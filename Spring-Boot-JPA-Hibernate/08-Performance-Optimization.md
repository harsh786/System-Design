# Performance Optimization - Interview Questions (Q156-Q175)

---

## Q156: What is the N+1 SELECT problem? How to detect it?

The **N+1 SELECT problem** occurs when Hibernate executes 1 query to fetch N parent entities, then N additional queries to fetch a related collection/association for each parent.

### Example

```java
@Entity
public class Author {
    @Id
    private Long id;
    private String name;

    @OneToMany(mappedBy = "author", fetch = FetchType.LAZY)
    private List<Book> books;
}
```

```java
// 1 query to fetch all authors
List<Author> authors = entityManager.createQuery("SELECT a FROM Author a", Author.class).getResultList();

// N queries - one for each author's books
for (Author author : authors) {
    System.out.println(author.getBooks().size()); // triggers lazy load
}
```

**Generated SQL:**
```sql
-- 1st query
SELECT * FROM author;

-- N queries (one per author)
SELECT * FROM book WHERE author_id = 1;
SELECT * FROM book WHERE author_id = 2;
SELECT * FROM book WHERE author_id = 3;
-- ... N times
```

### How to Detect

1. **Enable SQL logging:**
```properties
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true
```

2. **Enable statistics:**
```properties
spring.jpa.properties.hibernate.generate_statistics=true
```

3. **Use tools like:**
   - `datasource-proxy` library
   - Hibernate's `SessionMetrics`
   - P6Spy for SQL interception
   - Integration tests that assert query count

4. **Query count assertion (test):**
```java
@Test
void shouldNotHaveNPlusOne() {
    StatisticsImplementor stats = (StatisticsImplementor) sessionFactory.getStatistics();
    stats.clear();

    List<Author> authors = authorRepository.findAll();
    authors.forEach(a -> a.getBooks().size());

    // Should be 1 or 2, not N+1
    assertThat(stats.getQueryExecutionCount()).isLessThanOrEqualTo(2);
}
```

---

## Q157: How to solve N+1 problem? (JOIN FETCH, @EntityGraph, @BatchSize, @Fetch)

### Solution 1: JOIN FETCH (JPQL)

```java
@Query("SELECT a FROM Author a JOIN FETCH a.books")
List<Author> findAllWithBooks();
```

Generates a single SQL JOIN query:
```sql
SELECT a.*, b.* FROM author a LEFT JOIN book b ON a.id = b.author_id;
```

**Caveat:** With `JOIN FETCH` on collections, duplicates may appear. Use `DISTINCT`:
```java
@Query("SELECT DISTINCT a FROM Author a JOIN FETCH a.books")
List<Author> findAllWithBooks();
```

Add this to avoid the `DISTINCT` being passed to SQL:
```properties
spring.jpa.properties.hibernate.query.passDistinctThrough=false
```

### Solution 2: @EntityGraph

```java
public interface AuthorRepository extends JpaRepository<Author, Long> {

    @EntityGraph(attributePaths = {"books"})
    List<Author> findAll();
}
```

Or define a named entity graph:
```java
@Entity
@NamedEntityGraph(name = "Author.withBooks",
    attributeNodes = @NamedAttributeNode("books"))
public class Author { ... }
```

```java
@EntityGraph(value = "Author.withBooks", type = EntityGraph.EntityGraphType.LOAD)
List<Author> findAll();
```

### Solution 3: @BatchSize

```java
@Entity
public class Author {
    @OneToMany(mappedBy = "author")
    @BatchSize(size = 25)
    private List<Book> books;
}
```

Instead of N queries, Hibernate fetches in batches using `IN` clause:
```sql
SELECT * FROM book WHERE author_id IN (1, 2, 3, ..., 25);
```

### Solution 4: @Fetch(FetchMode.SUBSELECT)

```java
@Entity
public class Author {
    @OneToMany(mappedBy = "author")
    @Fetch(FetchMode.SUBSELECT)
    private List<Book> books;
}
```

Generates a subselect query:
```sql
SELECT * FROM book WHERE author_id IN (SELECT id FROM author);
```

### Comparison

| Approach | Queries | Memory | Pagination |
|----------|---------|--------|------------|
| JOIN FETCH | 1 | High (cartesian) | Breaks |
| @EntityGraph | 1 | High | Breaks |
| @BatchSize | 1 + ceil(N/batch) | Moderate | Works |
| SUBSELECT | 2 | Moderate | Works |

---

## Q158: What is @BatchSize annotation? How does batch fetching work?

`@BatchSize` tells Hibernate to fetch lazy associations in batches rather than one-by-one.

### Configuration

**On a collection:**
```java
@Entity
public class Department {
    @OneToMany(mappedBy = "department", fetch = FetchType.LAZY)
    @BatchSize(size = 20)
    private List<Employee> employees;
}
```

**On an entity class (affects all lazy references to this entity):**
```java
@Entity
@BatchSize(size = 20)
public class Employee {
    // ...
}
```

**Global default:**
```properties
spring.jpa.properties.hibernate.default_batch_fetch_size=16
```

### How it works

When Hibernate initializes a lazy collection, it looks for other uninitialized proxies/collections of the same type in the persistence context and loads them together:

```java
List<Department> departments = deptRepo.findAll(); // 1 query, returns 50 depts

// When first collection is accessed:
departments.get(0).getEmployees().size();
// Hibernate loads employees for up to 20 departments in one query:
// SELECT * FROM employee WHERE department_id IN (?, ?, ?, ... ?) -- 20 params
```

### Batch size selection

- Too small: still many queries
- Too large: large IN clauses, memory pressure
- Recommended: 10-50, commonly 16 or 25
- Hibernate uses a smart algorithm (powers of 2 + remainder) to minimize number of prepared statement variations

---

## Q159: What is @Fetch(FetchMode.SUBSELECT)?

`@Fetch(FetchMode.SUBSELECT)` loads a collection using a subselect that re-executes the original parent query.

```java
@Entity
public class Category {
    @OneToMany(mappedBy = "category", fetch = FetchType.LAZY)
    @Fetch(FetchMode.SUBSELECT)
    private List<Product> products;
}
```

### Behavior

```java
// Query 1: Load categories
List<Category> categories = em.createQuery(
    "SELECT c FROM Category c WHERE c.active = true", Category.class
).getResultList();
// SQL: SELECT * FROM category WHERE active = true

// Query 2: When any collection is accessed
categories.get(0).getProducts().size();
// SQL: SELECT * FROM product WHERE category_id IN
//        (SELECT id FROM category WHERE active = true)
```

### Key characteristics

- Always results in exactly **2 queries** total (parent + one subselect for all children)
- The subselect re-runs the original query - if original query was expensive, this doubles the cost
- Loads **ALL** children at once - no batch limit
- Works with pagination (unlike JOIN FETCH)
- Cannot be configured globally - must be per-association
- Hibernate-specific (not JPA standard)

### When to use

- When the parent query is cheap
- When you know you'll access most/all collections
- When you want guaranteed 2-query behavior without tuning batch sizes

---

## Q160: Explain LAZY loading best practices

### Best Practice 1: Default to LAZY everywhere

```java
@Entity
public class Order {
    @ManyToOne(fetch = FetchType.LAZY)  // Override default EAGER
    private Customer customer;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY) // default
    private List<OrderItem> items;

    @ManyToMany(fetch = FetchType.LAZY) // default
    private Set<Tag> tags;
}
```

> `@ManyToOne` and `@OneToOne` default to EAGER - always override to LAZY.

### Best Practice 2: Fetch eagerly at query time based on use case

```java
// Use case 1: List orders (no need for items)
@Query("SELECT o FROM Order o")
List<Order> findAllOrders();

// Use case 2: Order details (need items)
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.id = :id")
Optional<Order> findOrderWithItems(@Param("id") Long id);

// Use case 3: Order with customer info
@EntityGraph(attributePaths = {"customer"})
Optional<Order> findById(Long id);
```

### Best Practice 3: Use DTOs when you don't need entities

```java
@Query("SELECT new com.example.OrderSummaryDTO(o.id, o.total, c.name) " +
       "FROM Order o JOIN o.customer c")
List<OrderSummaryDTO> findOrderSummaries();
```

### Best Practice 4: Avoid accessing lazy associations outside transactions

```java
@Service
public class OrderService {
    @Transactional(readOnly = true)
    public OrderDTO getOrderDetails(Long id) {
        Order order = orderRepo.findOrderWithItems(id); // fetch what you need
        return mapper.toDTO(order); // map within transaction
    }
}
```

### Best Practice 5: Enable bytecode enhancement for lazy basic attributes

```xml
<plugin>
    <groupId>org.hibernate.orm.tooling</groupId>
    <artifactId>hibernate-enhance-maven-plugin</artifactId>
    <configuration>
        <enableLazyInitialization>true</enableLazyInitialization>
    </configuration>
</plugin>
```

```java
@Entity
public class Document {
    @Basic(fetch = FetchType.LAZY)
    @Column(columnDefinition = "TEXT")
    private String content; // Only loaded when accessed
}
```

### Best Practice 6: Avoid OSIV - disable it

```properties
spring.jpa.open-in-view=false
```

---

## Q161: What is LazyInitializationException? How to solve it?

`LazyInitializationException` is thrown when you access an uninitialized lazy association **outside** an active Hibernate Session/transaction.

```
org.hibernate.LazyInitializationException: could not initialize proxy - no Session
```

### Example that fails

```java
@Service
public class AuthorService {
    public List<String> getBookTitles(Long authorId) {
        Author author = authorRepo.findById(authorId).orElseThrow();
        // Transaction ends after findById (no @Transactional)
        return author.getBooks().stream()  // LazyInitializationException!
                .map(Book::getTitle)
                .toList();
    }
}
```

### Solutions

**1. Use @Transactional (keep session open)**
```java
@Transactional(readOnly = true)
public List<String> getBookTitles(Long authorId) {
    Author author = authorRepo.findById(authorId).orElseThrow();
    return author.getBooks().stream()
            .map(Book::getTitle)
            .toList();
}
```

**2. Fetch eagerly in the query (best approach)**
```java
@Query("SELECT a FROM Author a JOIN FETCH a.books WHERE a.id = :id")
Optional<Author> findByIdWithBooks(@Param("id") Long id);
```

**3. Use @EntityGraph**
```java
@EntityGraph(attributePaths = {"books"})
Optional<Author> findById(Long id);
```

**4. Use Hibernate.initialize()**
```java
@Transactional(readOnly = true)
public Author getAuthorWithBooks(Long id) {
    Author author = authorRepo.findById(id).orElseThrow();
    Hibernate.initialize(author.getBooks()); // force initialization
    return author;
}
```

**5. Use DTO projection (avoids the problem entirely)**
```java
@Query("SELECT new com.example.AuthorBooksDTO(a.name, b.title) " +
       "FROM Author a JOIN a.books b WHERE a.id = :id")
List<AuthorBooksDTO> findAuthorBooks(@Param("id") Long id);
```

### Anti-patterns to AVOID

- `FetchType.EAGER` - hides the problem but creates N+1 elsewhere
- `spring.jpa.open-in-view=true` (OSIV) - keeps session open in view layer, masks issues
- `hibernate.enable_lazy_load_no_trans=true` - opens new connections per lazy load, connection pool exhaustion risk

---

## Q162: What is the Open Session in View (OSIV) anti-pattern?

OSIV keeps the Hibernate Session open for the entire HTTP request lifecycle, including the view rendering phase (controller/serialization layer).

### How it works in Spring Boot

```
Request → Filter (opens Session) → Controller → Service → Repository → Controller (renders) → Filter (closes Session)
```

Spring Boot **enables OSIV by default** via `OpenEntityManagerInViewInterceptor`:
```properties
spring.jpa.open-in-view=true  # DEFAULT
```

You'll see this warning on startup:
```
WARN: spring.jpa.open-in-view is enabled by default. Therefore, database queries may be performed during view rendering.
```

### Why it's an anti-pattern

**1. Database connections held too long:**
```java
@GetMapping("/authors")
public List<AuthorDTO> getAuthors() {
    List<Author> authors = authorService.findAll();
    // Connection still held while Jackson serializes...
    // If serialization triggers lazy loads → more queries outside service layer
    return authors.stream().map(this::toDTO).toList();
}
```

**2. Lazy loads in the view layer are unpredictable:**
- JSON serialization may trigger N+1 queries in the controller
- No `@Transactional` boundary → queries run in auto-commit mode
- Hard to track where queries originate

**3. Connection pool exhaustion under load:**
- Connections held for full request duration (including slow view rendering)
- Fewer connections available for other requests

**4. Hides architectural issues:**
- Developers don't notice lazy loading problems during development
- Issues only surface under production load

### Recommended approach - disable OSIV

```properties
spring.jpa.open-in-view=false
```

Then follow proper patterns:
```java
@Service
public class AuthorService {
    @Transactional(readOnly = true)
    public List<AuthorDTO> getAuthorsWithBooks() {
        return authorRepo.findAllWithBooks().stream()
                .map(this::toDTO)  // map inside transaction
                .toList();
    }
}
```

---

## Q163: How to optimize bulk insert operations?

### Problem: Default behavior is slow

```java
// SLOW: 10,000 individual INSERTs
for (int i = 0; i < 10000; i++) {
    entityManager.persist(new Product("Product " + i));
}
```

### Solution 1: Batch inserts with periodic flush/clear

```properties
spring.jpa.properties.hibernate.jdbc.batch_size=50
spring.jpa.properties.hibernate.order_inserts=true
spring.jpa.properties.hibernate.order_updates=true
```

```java
@Transactional
public void bulkInsert(List<Product> products) {
    int batchSize = 50;
    for (int i = 0; i < products.size(); i++) {
        entityManager.persist(products.get(i));

        if (i % batchSize == 0 && i > 0) {
            entityManager.flush();  // Execute batch INSERT
            entityManager.clear(); // Free memory (detach entities)
        }
    }
}
```

### Solution 2: Use IDENTITY generation strategy workaround

**Problem:** `GenerationType.IDENTITY` disables JDBC batching because Hibernate needs the generated ID immediately.

**Fix:** Use `SEQUENCE` with allocationSize:
```java
@Entity
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "product_seq")
    @SequenceGenerator(name = "product_seq", sequenceName = "product_seq", allocationSize = 50)
    private Long id;
}
```

### Solution 3: Spring Data JPA saveAll with batching

```java
@Transactional
public void batchSave(List<Product> products) {
    List<List<Product>> batches = Lists.partition(products, 1000);
    for (List<Product> batch : batches) {
        productRepository.saveAll(batch);
        entityManager.flush();
        entityManager.clear();
    }
}
```

### Solution 4: Native JDBC batch for maximum performance

```java
@Transactional
public void jdbcBulkInsert(List<Product> products) {
    jdbcTemplate.batchUpdate(
        "INSERT INTO product (name, price, category_id) VALUES (?, ?, ?)",
        products,
        1000,
        (ps, product) -> {
            ps.setString(1, product.getName());
            ps.setBigDecimal(2, product.getPrice());
            ps.setLong(3, product.getCategoryId());
        }
    );
}
```

### Solution 5: Use StatelessSession for no persistence context overhead

```java
@Transactional
public void statelessBulkInsert(List<Product> products) {
    StatelessSession statelessSession = sessionFactory.openStatelessSession();
    Transaction tx = statelessSession.beginTransaction();
    try {
        for (Product product : products) {
            statelessSession.insert(product);
        }
        tx.commit();
    } catch (Exception e) {
        tx.rollback();
        throw e;
    } finally {
        statelessSession.close();
    }
}
```

### Performance comparison (10,000 inserts)

| Approach | Time (approx) |
|----------|---------------|
| Default (no batching) | ~15s |
| Batch size=50 + flush/clear | ~3s |
| JDBC batch | ~1s |
| StatelessSession | ~1.5s |
| Native COPY (PostgreSQL) | ~0.2s |

---

## Q164: How to optimize bulk update/delete operations?

### Problem: Entity-by-entity updates

```java
// SLOW: Loads all entities, modifies each, generates N UPDATE statements
@Transactional
public void deactivateOldProducts() {
    List<Product> products = productRepo.findByCreatedDateBefore(cutoff);
    products.forEach(p -> p.setActive(false)); // N dirty-checking UPDATEs
}
```

### Solution 1: JPQL Bulk Update/Delete

```java
@Modifying
@Query("UPDATE Product p SET p.active = false WHERE p.createdDate < :cutoff")
int deactivateOldProducts(@Param("cutoff") LocalDate cutoff);

@Modifying
@Query("DELETE FROM Product p WHERE p.active = false AND p.createdDate < :cutoff")
int deleteOldInactiveProducts(@Param("cutoff") LocalDate cutoff);
```

**Important:** Bulk operations bypass the persistence context. Add `clearAutomatically`:
```java
@Modifying(clearAutomatically = true, flushAutomatically = true)
@Query("UPDATE Product p SET p.price = p.price * :factor WHERE p.category = :cat")
int updatePrices(@Param("factor") BigDecimal factor, @Param("cat") Category cat);
```

### Solution 2: Criteria API Bulk Operations (JPA 2.1+)

```java
@Transactional
public int bulkUpdateWithCriteria(BigDecimal factor, String category) {
    CriteriaBuilder cb = entityManager.getCriteriaBuilder();
    CriteriaUpdate<Product> update = cb.createCriteriaUpdate(Product.class);
    Root<Product> root = update.from(Product.class);

    update.set(root.get("price"),
        cb.prod(root.get("price"), factor));
    update.where(cb.equal(root.get("category"), category));

    return entityManager.createQuery(update).executeUpdate();
}
```

### Solution 3: Native query for complex bulk operations

```java
@Modifying
@Query(value = "UPDATE product SET price = price * 1.1 " +
       "WHERE category_id IN (SELECT id FROM category WHERE name = :cat)",
       nativeQuery = true)
int bulkUpdateNative(@Param("cat") String category);
```

### Solution 4: Batch updates with JDBC

```java
@Transactional
public void batchUpdate(List<PriceUpdate> updates) {
    jdbcTemplate.batchUpdate(
        "UPDATE product SET price = ? WHERE id = ?",
        updates,
        500,
        (ps, update) -> {
            ps.setBigDecimal(1, update.getNewPrice());
            ps.setLong(2, update.getProductId());
        }
    );
}
```

### Solution 5: Hibernate batch update configuration

```properties
spring.jpa.properties.hibernate.jdbc.batch_size=50
spring.jpa.properties.hibernate.order_updates=true
spring.jpa.properties.hibernate.batch_versioned_data=true
```

```java
@Transactional
public void batchEntityUpdate(List<Long> ids) {
    int batchSize = 50;
    for (int i = 0; i < ids.size(); i += batchSize) {
        List<Long> batchIds = ids.subList(i, Math.min(i + batchSize, ids.size()));
        List<Product> products = productRepo.findAllById(batchIds);
        products.forEach(p -> p.setActive(false));
        entityManager.flush();
        entityManager.clear();
    }
}
```

---

## Q165: What is StatelessSession in Hibernate? When to use it?

`StatelessSession` is a Hibernate-specific API that provides a command-oriented, low-level interface without:
- First-level cache (persistence context)
- Dirty checking
- Cascading
- Interceptors/event listeners
- Lazy loading of associations

### Usage

```java
@Autowired
private EntityManagerFactory emf;

public void processLargeDataset() {
    SessionFactory sessionFactory = emf.unwrap(SessionFactory.class);

    try (StatelessSession session = sessionFactory.openStatelessSession()) {
        Transaction tx = session.beginTransaction();

        // Insert
        session.insert(new Product("Widget", BigDecimal.TEN));

        // Update (must pass the full entity)
        Product product = (Product) session.get(Product.class, 1L);
        product.setPrice(BigDecimal.valueOf(20));
        session.update(product);

        // Delete
        session.delete(product);

        // ScrollableResults for reading large datasets
        try (ScrollableResults<Product> scroll = session.createQuery(
                "FROM Product", Product.class).scroll(ScrollMode.FORWARD_ONLY)) {
            while (scroll.next()) {
                Product p = scroll.get();
                // process without accumulating in memory
            }
        }

        tx.commit();
    }
}
```

### When to use

| Use Case | StatelessSession | Regular Session |
|----------|-----------------|-----------------|
| Bulk inserts (ETL) | ✅ | ❌ (memory) |
| Batch processing large datasets | ✅ | ❌ |
| Read-only streaming | ✅ | ❌ |
| Complex entity graphs | ❌ | ✅ |
| Cascade operations | ❌ | ✅ |
| Lazy loading needed | ❌ | ✅ |
| Dirty checking needed | ❌ | ✅ |

### Caveats

- No automatic dirty checking - you must explicitly call `update()`
- No cascading - manage associations manually
- Accessing lazy associations throws exceptions
- No first-level cache - same entity loaded twice = two separate objects
- No optimistic locking check unless you handle versioning manually

---

## Q166: How to enable and analyze Hibernate SQL logging?

### Basic SQL Logging

```properties
# Show SQL (formatted)
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true

# Log through SLF4J (preferred over show-sql)
logging.level.org.hibernate.SQL=DEBUG
logging.level.org.hibernate.type.descriptor.sql.BasicBinder=TRACE
```

**Hibernate 6+ (Spring Boot 3):**
```properties
logging.level.org.hibernate.SQL=DEBUG
logging.level.org.hibernate.orm.jdbc.bind=TRACE
```

### Output example

```sql
DEBUG org.hibernate.SQL:
    select
        a1_0.id,
        a1_0.name
    from
        author a1_0
    where
        a1_0.id=?

TRACE org.hibernate.orm.jdbc.bind: binding parameter (1:BIGINT) <- [42]
```

### Using P6Spy for full SQL with parameters

```xml
<dependency>
    <groupId>com.github.gavlyukovskiy</groupId>
    <artifactId>p6spy-spring-boot-starter</artifactId>
    <version>1.9.0</version>
</dependency>
```

```properties
# spy.properties
appender=com.p6spy.engine.spy.appender.Slf4JLogger
logMessageFormat=com.p6spy.engine.spy.appender.CustomLineFormat
customLogMessageFormat=%(executionTime)ms | %(sql)
```

### Using datasource-proxy (query counting)

```java
@Configuration
public class DataSourceProxyConfig {

    @Bean
    public DataSource dataSource(DataSource originalDataSource) {
        return ProxyDataSourceBuilder.create(originalDataSource)
                .name("QueryCounter")
                .countQuery()
                .logQueryBySlf4j(SLF4JLogLevel.INFO)
                .build();
    }
}
```

### Assertion in tests

```java
@Test
void shouldExecuteOnlyTwoQueries() {
    QueryCountHolder.clear();

    authorService.getAuthorsWithBooks();

    QueryCount queryCount = QueryCountHolder.getGrandTotal();
    assertThat(queryCount.getSelect()).isEqualTo(2);
}
```

---

## Q167: What is hibernate.generate_statistics? How to use it for tuning?

`hibernate.generate_statistics` enables detailed performance metrics collection in Hibernate.

### Enable

```properties
spring.jpa.properties.hibernate.generate_statistics=true
logging.level.org.hibernate.stat=DEBUG
```

### Output example

```
Session Metrics {
    1200000 nanoseconds spent acquiring 5 JDBC connections;
    800000 nanoseconds spent releasing 5 JDBC connections;
    12000000 nanoseconds spent preparing 12 JDBC statements;
    45000000 nanoseconds spent executing 12 JDBC statements;
    0 nanoseconds spent executing 0 JDBC batches;
    0 nanoseconds spent performing 0 L2C puts;
    0 nanoseconds spent performing 0 L2C hits;
    0 nanoseconds spent performing 0 L2C misses;
    5000000 nanoseconds spent executing 1 flushes (flushing 50 entities and 25 collections);
    0 nanoseconds spent executing 0 partial-flushes;
}
```

### Programmatic access

```java
@Autowired
private EntityManagerFactory emf;

public void logStatistics() {
    Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();

    log.info("Queries executed: {}", stats.getQueryExecutionCount());
    log.info("Slowest query: {} ({}ms)", stats.getQueryExecutionMaxTimeQueryString(),
             stats.getQueryExecutionMaxTime());
    log.info("Second-level cache hit ratio: {}",
             stats.getSecondLevelCacheHitCount() /
             (double)(stats.getSecondLevelCacheHitCount() + stats.getSecondLevelCacheMissCount()));
    log.info("Entities loaded: {}", stats.getEntityLoadCount());
    log.info("Collections loaded: {}", stats.getCollectionLoadCount());

    stats.clear(); // Reset for next measurement period
}
```

### Expose via Spring Boot Actuator

```properties
management.endpoints.web.exposure.include=metrics
```

Hibernate metrics are auto-exposed as Micrometer metrics:
- `hibernate.sessions.open`
- `hibernate.statements`
- `hibernate.query.executions`
- `hibernate.cache.second.level.hits`
- `hibernate.entities.inserts`

### What to look for

| Metric | Warning Sign |
|--------|-------------|
| Query execution count | Unexpectedly high = N+1 |
| Slow queries | Optimize with indexes/fetch strategy |
| Cache miss ratio > 80% | Review cache configuration |
| Flush entity count | Too many entities in persistence context |
| Batch count = 0 | Batching not working |

> **Important:** Disable statistics in production (performance overhead ~5-10%) or sample periodically.

---

## Q168: How to use database connection pooling effectively (HikariCP configuration)?

Spring Boot uses **HikariCP** by default. Proper configuration is critical for performance.

### Key Configuration

```properties
# Pool sizing
spring.datasource.hikari.maximum-pool-size=20
spring.datasource.hikari.minimum-idle=5

# Timeouts
spring.datasource.hikari.connection-timeout=30000    # 30s - wait for connection from pool
spring.datasource.hikari.idle-timeout=600000         # 10min - idle connection eviction
spring.datasource.hikari.max-lifetime=1800000        # 30min - max connection age
spring.datasource.hikari.keepalive-time=300000       # 5min - keepalive ping

# Validation
spring.datasource.hikari.validation-timeout=5000

# Leak detection
spring.datasource.hikari.leak-detection-threshold=60000  # Warn if connection held > 60s

# Pool name (useful for monitoring)
spring.datasource.hikari.pool-name=MyAppPool
```

### Pool Size Formula

**Recommended formula (from HikariCP wiki):**
```
connections = ((core_count * 2) + effective_spindle_count)
```

For most applications with SSDs:
- 4 cores → ~10 connections is a good starting point
- Maximum should rarely exceed 20-30

### Common Mistakes

**1. Pool too large:**
```properties
# BAD - too many connections cause context switching overhead
spring.datasource.hikari.maximum-pool-size=100
```

**2. No leak detection:**
```properties
# GOOD - detect connection leaks during development
spring.datasource.hikari.leak-detection-threshold=30000
```

**3. OSIV holding connections too long:**
```properties
# FIX: disable OSIV
spring.jpa.open-in-view=false
```

### Monitoring

```java
@Autowired
private DataSource dataSource;

@Scheduled(fixedRate = 60000)
public void logPoolStats() {
    HikariDataSource hds = (HikariDataSource) dataSource;
    HikariPoolMXBean pool = hds.getHikariPoolMXBean();

    log.info("Pool stats - Active: {}, Idle: {}, Waiting: {}, Total: {}",
        pool.getActiveConnections(),
        pool.getIdleConnections(),
        pool.getThreadsAwaitingConnection(),
        pool.getTotalConnections());
}
```

### Spring Boot Actuator metrics

```properties
management.endpoints.web.exposure.include=health,metrics
management.health.db.enabled=true
```

Available metrics:
- `hikaricp.connections.active`
- `hikaricp.connections.idle`
- `hikaricp.connections.pending`
- `hikaricp.connections.timeout`

---

## Q169: What is the impact of FetchType on performance?

### FetchType.EAGER

- Association loaded **immediately** with the parent entity
- Uses JOIN or secondary SELECT depending on Hibernate strategy
- **Cannot be overridden to LAZY at query time**

```java
@ManyToOne(fetch = FetchType.EAGER)  // Always loaded
private Category category;
```

**Performance impact:**
- Loads data you may not need
- Causes Cartesian product with multiple EAGER collections
- Triggers N+1 when loading lists of entities
- Cannot be made lazy per-query

### FetchType.LAZY

- Association loaded **on demand** when first accessed
- Returns a proxy object initially
- **Can be overridden to EAGER at query time** (JOIN FETCH, EntityGraph)

```java
@ManyToOne(fetch = FetchType.LAZY)
private Category category;
```

**Performance impact:**
- Only loads data when needed
- Risk of N+1 if accessed in a loop without prefetching
- Risk of LazyInitializationException outside transaction

### Default FetchTypes

| Annotation | Default |
|------------|---------|
| `@OneToOne` | EAGER |
| `@ManyToOne` | EAGER |
| `@OneToMany` | LAZY |
| `@ManyToMany` | LAZY |

### The Cartesian Product Problem

```java
@Entity
public class Author {
    @OneToMany(fetch = FetchType.EAGER)
    private List<Book> books;       // 5 books

    @OneToMany(fetch = FetchType.EAGER)
    private List<Award> awards;     // 3 awards
}

// Loading 1 Author → Cartesian product: 5 × 3 = 15 rows!
```

### Best Practice

```java
// ALWAYS use LAZY, then fetch per use case
@ManyToOne(fetch = FetchType.LAZY)
private Category category;

// Query 1: Don't need category
List<Product> products = productRepo.findAll();

// Query 2: Need category
@EntityGraph(attributePaths = {"category"})
List<Product> findAllWithCategory();
```

---

## Q170: How to use DTO projections for read-only queries (performance benefit)?

DTO projections avoid the overhead of managed entities: no dirty checking, no proxy creation, no persistence context storage.

### Interface-based Projection (Spring Data)

```java
// Closed projection
public interface AuthorSummary {
    String getName();
    int getBookCount();
}

public interface AuthorRepository extends JpaRepository<Author, Long> {
    @Query("SELECT a.name as name, SIZE(a.books) as bookCount FROM Author a")
    List<AuthorSummary> findAllSummaries();
}
```

### Class-based DTO Projection (JPQL Constructor Expression)

```java
public record OrderSummaryDTO(Long id, String customerName, BigDecimal total, LocalDate orderDate) {}

@Query("SELECT new com.example.dto.OrderSummaryDTO(o.id, c.name, o.total, o.orderDate) " +
       "FROM Order o JOIN o.customer c WHERE o.status = :status")
List<OrderSummaryDTO> findOrderSummaries(@Param("status") OrderStatus status);
```

### Tuple Projection

```java
@Query("SELECT o.id, o.total, c.name FROM Order o JOIN o.customer c")
List<Tuple> findOrderTuples();

// Usage
tuples.forEach(t -> {
    Long id = t.get(0, Long.class);
    BigDecimal total = t.get(1, BigDecimal.class);
});
```

### Native Query with DTO

```java
@Query(value = "SELECT id, customer_name, total FROM orders WHERE status = :status",
       nativeQuery = true)
List<OrderSummaryProjection> findNativeProjection(@Param("status") String status);
```

### Performance Benefits

| Aspect | Entity Query | DTO Projection |
|--------|-------------|----------------|
| Memory | Full entity + proxy | Only selected fields |
| Dirty checking | Yes (overhead) | None |
| Persistence context | Managed | Not managed |
| SQL | SELECT * | SELECT specific columns |
| Network | All columns | Only needed columns |

### Benchmark (typical)

- Entity: 100ms for 10,000 rows
- DTO: 40ms for 10,000 rows (60% faster)

### Spring Data JPA dynamic projections

```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    <T> List<T> findByCategory(String category, Class<T> type);
}

// Usage
List<ProductSummary> summaries = productRepo.findByCategory("electronics", ProductSummary.class);
List<Product> full = productRepo.findByCategory("electronics", Product.class);
```

---

## Q171: What is the difference between JPQL JOIN FETCH and @EntityGraph performance-wise?

### SQL Generation

Both produce LEFT JOIN queries, but with subtle differences:

**JOIN FETCH:**
```java
@Query("SELECT a FROM Author a JOIN FETCH a.books WHERE a.active = true")
List<Author> findActiveAuthorsWithBooks();
```
```sql
SELECT a.*, b.* FROM author a
INNER JOIN book b ON a.id = b.author_id
WHERE a.active = true
```

**@EntityGraph:**
```java
@EntityGraph(attributePaths = {"books"})
List<Author> findByActiveTrue();
```
```sql
SELECT a.*, b.* FROM author a
LEFT JOIN book b ON a.id = b.author_id
WHERE a.active = true
```

### Key Differences

| Aspect | JOIN FETCH | @EntityGraph |
|--------|-----------|--------------|
| Join type | INNER JOIN (default) | LEFT JOIN (always) |
| NULL parents | Excluded (no match) | Included |
| Multiple collections | Supports (with caveats) | Supports |
| Dynamic conditions | Yes (WHERE on joined entity) | No |
| Pagination | **Broken** (in-memory) | **Broken** (in-memory) |
| Composability | Part of query string | Declarative, reusable |
| Subgraph support | Nested JOIN FETCH | `@NamedSubgraph` |

### Pagination Problem (both affected)

```java
// WARNING: Pagination + JOIN FETCH = full result in memory
@Query("SELECT a FROM Author a JOIN FETCH a.books")
Page<Author> findAll(Pageable pageable);
// Hibernate WARNING: HHH90003004: firstResult/maxResults specified with collection fetch; applying in memory!
```

**Fix:** Use two queries:
```java
// Query 1: Get paginated IDs
@Query("SELECT a.id FROM Author a WHERE a.active = true")
Page<Long> findActiveAuthorIds(Pageable pageable);

// Query 2: Fetch entities with associations by IDs
@Query("SELECT a FROM Author a JOIN FETCH a.books WHERE a.id IN :ids")
List<Author> findByIdInWithBooks(@Param("ids") List<Long> ids);
```

### When to use which

- **JOIN FETCH:** When you need INNER JOIN semantics, filtering on the association, or full JPQL control
- **@EntityGraph:** When you want reusable, declarative eager loading on existing Spring Data methods without modifying the query

---

## Q172: How to handle large result sets efficiently (Streaming, ScrollableResults)?

### Problem: Loading millions of rows into memory

```java
// BAD: loads all into memory at once
List<Product> all = productRepo.findAll(); // OutOfMemoryError with millions of rows
```

### Solution 1: Java 8 Stream (Spring Data)

```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    @QueryHints(@QueryHint(name = HINT_FETCH_SIZE, value = "50"))
    Stream<Product> findAllByCategory(String category);
}
```

```java
@Transactional(readOnly = true)
public void processAllProducts(String category) {
    try (Stream<Product> stream = productRepo.findAllByCategory(category)) {
        stream.forEach(product -> {
            processProduct(product);
            entityManager.detach(product); // free memory
        });
    }
}
```

### Solution 2: ScrollableResults (Hibernate)

```java
@Transactional(readOnly = true)
public void processWithScroll() {
    Session session = entityManager.unwrap(Session.class);

    try (ScrollableResults<Product> scroll = session.createQuery(
            "FROM Product p WHERE p.active = true", Product.class)
            .setFetchSize(100)
            .setReadOnly(true)
            .scroll(ScrollMode.FORWARD_ONLY)) {

        int count = 0;
        while (scroll.next()) {
            Product product = scroll.get();
            processProduct(product);

            if (++count % 100 == 0) {
                entityManager.clear(); // Prevent persistence context from growing
            }
        }
    }
}
```

### Solution 3: Pagination (Slice-based)

```java
@Transactional(readOnly = true)
public void processInPages() {
    Pageable pageable = PageRequest.of(0, 500, Sort.by("id"));
    Slice<Product> slice;

    do {
        slice = productRepo.findByActiveTrue(pageable);
        slice.getContent().forEach(this::processProduct);
        entityManager.clear();
        pageable = slice.nextPageable();
    } while (slice.hasNext());
}
```

### Solution 4: Keyset Pagination (most efficient for large offsets)

```java
@Query("SELECT p FROM Product p WHERE p.id > :lastId ORDER BY p.id ASC")
List<Product> findNextBatch(@Param("lastId") Long lastId, Pageable pageable);
```

```java
@Transactional(readOnly = true)
public void processWithKeyset() {
    Long lastId = 0L;
    List<Product> batch;

    do {
        batch = productRepo.findNextBatch(lastId, PageRequest.of(0, 500));
        batch.forEach(this::processProduct);
        if (!batch.isEmpty()) {
            lastId = batch.get(batch.size() - 1).getId();
        }
        entityManager.clear();
    } while (!batch.isEmpty());
}
```

### Solution 5: StatelessSession for pure read-through

```java
public void streamWithStatelessSession() {
    SessionFactory sf = emf.unwrap(SessionFactory.class);
    try (StatelessSession session = sf.openStatelessSession()) {
        try (ScrollableResults<Product> scroll = session.createQuery(
                "FROM Product", Product.class)
                .setFetchSize(100)
                .scroll(ScrollMode.FORWARD_ONLY)) {
            while (scroll.next()) {
                processProduct(scroll.get());
                // No persistence context to clear!
            }
        }
    }
}
```

### Comparison

| Approach | Memory | Speed | Complexity |
|----------|--------|-------|------------|
| findAll() | O(N) | Slow for large N | Simple |
| Stream | O(batch) | Good | Low |
| ScrollableResults | O(batch) | Good | Medium |
| Slice pagination | O(page) | Slower (offset) | Low |
| Keyset pagination | O(page) | Fast | Medium |
| StatelessSession scroll | O(1) | Fastest | High |

---

## Q173: What is database indexing and how does it relate to JPA/Hibernate?

### What are indexes?

Indexes are data structures (typically B-tree) that speed up data retrieval at the cost of additional storage and slower writes.

### Defining indexes with JPA

**Single column index:**
```java
@Entity
@Table(name = "product", indexes = {
    @Index(name = "idx_product_name", columnList = "name"),
    @Index(name = "idx_product_sku", columnList = "sku", unique = true)
})
public class Product {
    @Id
    private Long id;
    private String name;
    private String sku;
}
```

**Composite index:**
```java
@Table(indexes = {
    @Index(name = "idx_order_customer_date", columnList = "customer_id, order_date DESC")
})
public class Order { ... }
```

**Using @Column unique (creates implicit index):**
```java
@Column(unique = true)
private String email;
```

### When indexes matter in JPA/Hibernate

**1. Foreign key columns (JOIN operations):**
```java
@ManyToOne(fetch = FetchType.LAZY)
@JoinColumn(name = "category_id") // Should be indexed
private Category category;
```

Most databases auto-index FK constraints, but MySQL InnoDB does, PostgreSQL does NOT.

**2. Columns used in WHERE clauses:**
```java
@Query("SELECT p FROM Product p WHERE p.status = :status AND p.createdDate > :date")
List<Product> findActiveRecent(...);
// Index on (status, created_date) would help
```

**3. Columns used in ORDER BY:**
```java
productRepo.findAll(Sort.by("name")); // Index on name helps
```

**4. Columns used in JPQL/Criteria predicates:**
```java
// Composite index on (tenant_id, active) covers this query
@Query("SELECT p FROM Product p WHERE p.tenantId = :tid AND p.active = true")
List<Product> findByTenant(@Param("tid") Long tenantId);
```

### Index Gotchas with Hibernate

- `hibernate.hbm2ddl.auto=update` creates indexes from `@Index` annotations
- For production, manage indexes via Flyway/Liquibase migrations
- Discriminator columns in inheritance (`@DiscriminatorColumn`) should be indexed
- `@Version` columns don't need indexing (used in WHERE of UPDATE, not SELECT)

### Best practices

- Index FK columns explicitly (don't rely on auto-creation)
- Create composite indexes matching your query patterns (column order matters)
- Don't over-index: each index slows INSERT/UPDATE
- Use `EXPLAIN ANALYZE` to verify index usage
- Consider partial/filtered indexes for frequently queried subsets

---

## Q174: How to use @DynamicUpdate and @DynamicInsert for performance?

### @DynamicUpdate

By default, Hibernate generates UPDATE statements that set **all columns**, regardless of which changed. `@DynamicUpdate` generates SQL that only includes **modified columns**.

```java
@Entity
@DynamicUpdate
public class Product {
    @Id
    private Long id;
    private String name;
    private BigDecimal price;
    private String description;
    private boolean active;
    // ... 20 more fields
}
```

**Without @DynamicUpdate:**
```sql
UPDATE product SET name=?, price=?, description=?, active=?, ... WHERE id=?
-- All 20+ columns always included
```

**With @DynamicUpdate (only price changed):**
```sql
UPDATE product SET price=? WHERE id=?
```

### When @DynamicUpdate helps

- Tables with many columns (wide tables)
- Only a few columns change per update
- Reduces redo log / WAL size
- Avoids unnecessary index updates on unchanged indexed columns
- Optimistic locking with `@OptimisticLock(excluded = true)` on some fields

### When @DynamicUpdate hurts

- Prevents Hibernate from caching a single prepared statement per entity
- Each unique combination of changed columns = new SQL statement
- With few columns, the overhead isn't worth it
- Increases PreparedStatement cache pressure

### @DynamicInsert

Generates INSERT SQL with only non-null columns, allowing database defaults to apply.

```java
@Entity
@DynamicInsert
public class AuditLog {
    @Id @GeneratedValue
    private Long id;

    private String action;
    private String details;

    @Column(insertable = false) // or just rely on @DynamicInsert
    private LocalDateTime createdAt; // DB default: CURRENT_TIMESTAMP

    @Column(insertable = false)
    private String status; // DB default: 'PENDING'
}
```

**Without @DynamicInsert:**
```sql
INSERT INTO audit_log (action, details, created_at, status) VALUES (?, ?, NULL, NULL)
-- Overrides DB defaults with NULL!
```

**With @DynamicInsert:**
```sql
INSERT INTO audit_log (action, details) VALUES (?, ?)
-- DB defaults apply for created_at and status
```

### Summary

| Annotation | Use When | Avoid When |
|------------|----------|------------|
| `@DynamicUpdate` | Wide tables, few columns change | Narrow tables, high update rate |
| `@DynamicInsert` | DB defaults needed, sparse inserts | All columns always provided |

---

## Q175: What are Hibernate performance monitoring tools and best practices?

### Built-in Tools

**1. Hibernate Statistics (see Q167)**
```properties
spring.jpa.properties.hibernate.generate_statistics=true
```

**2. Slow query log**
```properties
spring.jpa.properties.hibernate.session.events.log.LOG_QUERIES_SLOWER_THAN_MS=25
```

### Third-Party Tools

**3. P6Spy - SQL logging with timing**
```xml
<dependency>
    <groupId>com.github.gavlyukovskiy</groupId>
    <artifactId>p6spy-spring-boot-starter</artifactId>
    <version>1.9.0</version>
</dependency>
```

**4. datasource-proxy - query counting and assertion**
```java
ProxyDataSourceBuilder.create(dataSource)
    .countQuery()
    .logQueryBySlf4j()
    .afterQuery((execInfo, queryInfoList) -> {
        if (execInfo.getElapsedTime() > 1000) {
            log.warn("Slow query: {}ms - {}", execInfo.getElapsedTime(),
                queryInfoList.get(0).getQuery());
        }
    })
    .build();
```

**5. Spring Boot Actuator + Micrometer**
```properties
management.endpoints.web.exposure.include=metrics,health
management.metrics.enable.hibernate=true
```

Exposes:
- `hibernate.sessions.open`
- `hibernate.query.executions`
- `hibernate.cache.*`
- `hikaricp.connections.*`

**6. Grafana + Prometheus dashboards** for visualizing the above metrics over time.

### Performance Best Practices Checklist

| # | Practice | Impact |
|---|----------|--------|
| 1 | All associations LAZY by default | High |
| 2 | Disable OSIV | High |
| 3 | Use DTO projections for read queries | High |
| 4 | Enable JDBC batching (batch_size=25-50) | High |
| 5 | Use JOIN FETCH / @EntityGraph per use case | High |
| 6 | Enable second-level cache for read-heavy entities | Medium |
| 7 | Use @BatchSize or SUBSELECT for collections | Medium |
| 8 | Index FK columns and query predicates | High |
| 9 | Use bulk operations for mass updates/deletes | High |
| 10 | Use connection pool monitoring & right-size pool | Medium |
| 11 | Use @DynamicUpdate for wide tables | Low-Medium |
| 12 | Use StatelessSession for batch/ETL | Medium |
| 13 | Stream/scroll large result sets | Medium |
| 14 | Use read-only transactions for queries | Low |
| 15 | Monitor with statistics + slow query log | Essential |

### Test-time validation

```java
@SpringBootTest
@TestPropertySource(properties = "spring.jpa.properties.hibernate.generate_statistics=true")
class PerformanceTest {

    @Autowired
    private EntityManagerFactory emf;

    @Test
    void verifyQueryCount() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        stats.clear();

        // Execute business operation
        orderService.getOrderDashboard();

        assertThat(stats.getQueryExecutionCount())
            .as("Expected max 3 queries for dashboard")
            .isLessThanOrEqualTo(3);

        assertThat(stats.getEntityFetchCount())
            .as("No additional entity fetches (N+1 check)")
            .isZero();
    }
}
```

### Production Monitoring Strategy

1. **Enable slow query logging** (>25ms threshold)
2. **Export Hibernate metrics to Prometheus/Grafana**
3. **Set connection pool leak detection** (60s threshold)
4. **Alert on high `threads_awaiting_connection`** (pool saturation)
5. **Periodically review query execution counts** vs expected
6. **Use APM tools** (New Relic, Datadog, Application Insights) for distributed tracing of DB calls
