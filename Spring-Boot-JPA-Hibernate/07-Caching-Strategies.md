# Caching Strategies - Interview Questions (Q136-Q155)

---

## Q136: What is caching in Hibernate? Why is it needed?

**Answer:**

Caching in Hibernate is a mechanism to store frequently accessed data in memory to reduce database round-trips, improving application performance significantly.

### Why Caching is Needed:

1. **Reduce DB load** – Fewer SQL queries hit the database
2. **Improve response time** – In-memory access is orders of magnitude faster than disk I/O
3. **Scalability** – Application can handle more concurrent users
4. **Network latency** – Eliminates repeated network calls to the DB server

### Hibernate Cache Architecture:

```
Application
    │
    ▼
┌─────────────────┐
│  First-Level    │  (Session Cache - per session)
│  Cache          │
└────────┬────────┘
         │ (miss)
         ▼
┌─────────────────┐
│  Second-Level   │  (SessionFactory Cache - shared)
│  Cache          │
└────────┬────────┘
         │ (miss)
         ▼
┌─────────────────┐
│  Query Cache    │  (Caches query results)
└────────┬────────┘
         │ (miss)
         ▼
┌─────────────────┐
│   Database      │
└─────────────────┘
```

### Example demonstrating cache benefit:

```java
// Without cache: 2 SQL queries
Session session = sessionFactory.openSession();
Employee emp1 = session.get(Employee.class, 1L); // SQL fired
session.close();

Session session2 = sessionFactory.openSession();
Employee emp2 = session2.get(Employee.class, 1L); // SQL fired again
session2.close();

// With second-level cache: only 1 SQL query
// The second get() reads from cache
```

---

## Q137: Explain First-Level Cache (Session Cache) in detail

**Answer:**

The First-Level Cache is associated with the Hibernate `Session` object. It is the default cache and stores entities within the scope of a single session/transaction.

### Key Characteristics:

- **Scope:** Per `Session` (transaction-scoped)
- **Enabled by default:** Always on, cannot be disabled
- **Storage:** Stores entity objects by their identifier (primary key)
- **Lifecycle:** Lives as long as the session is open
- **Thread-safety:** Not thread-safe (session is not thread-safe)

### How it works:

```java
Session session = sessionFactory.openSession();
Transaction tx = session.beginTransaction();

// First call - SQL SELECT fired, entity stored in first-level cache
Employee emp1 = session.get(Employee.class, 1L);
System.out.println(emp1.getName());

// Second call - NO SQL, returned from first-level cache
Employee emp2 = session.get(Employee.class, 1L);
System.out.println(emp2.getName());

// Both references point to the same object
System.out.println(emp1 == emp2); // true (same instance)

tx.commit();
session.close();
```

### Persistence Context Identity Guarantee:

The first-level cache ensures that within a session, only one instance of an entity with a given identifier exists. This is the **repeatable read** guarantee at the application level.

### Managing First-Level Cache:

```java
// Evict a specific entity from first-level cache
session.evict(employee);

// Clear entire first-level cache
session.clear();

// Check if entity is in cache
boolean cached = session.contains(employee);

// Refresh entity from DB (bypasses cache)
session.refresh(employee);
```

### Batch Processing with First-Level Cache:

```java
Session session = sessionFactory.openSession();
Transaction tx = session.beginTransaction();

for (int i = 0; i < 100000; i++) {
    Employee emp = new Employee("Emp" + i);
    session.save(emp);
    
    // Flush and clear every 50 records to prevent OutOfMemoryError
    if (i % 50 == 0) {
        session.flush();
        session.clear();
    }
}

tx.commit();
session.close();
```

---

## Q138: Is First-Level Cache enabled by default? Can it be disabled?

**Answer:**

**Yes**, the First-Level Cache is **always enabled by default** and **cannot be disabled**. It is an integral part of Hibernate's architecture and the persistence context.

### Why it cannot be disabled:

1. It implements the **Identity Map** pattern – guarantees `a == b` for same entity within a session
2. It enables **dirty checking** – Hibernate compares current state with snapshot in cache
3. It implements **Unit of Work** pattern – tracks all changes for batch flush
4. It prevents **phantom reads** within a session

### What you CAN do:

```java
// 1. Evict specific entity
session.evict(entity);

// 2. Clear entire session cache
session.clear();

// 3. Use StatelessSession (no first-level cache)
StatelessSession statelessSession = sessionFactory.openStatelessSession();
Transaction tx = statelessSession.beginTransaction();

Employee emp = (Employee) statelessSession.get(Employee.class, 1L);
// No caching, no dirty checking, no cascades
emp.setName("Updated");
statelessSession.update(emp); // Explicit update required

tx.commit();
statelessSession.close();
```

### StatelessSession characteristics:

- No first-level cache
- No dirty checking
- No cascading
- No interceptors or event listeners
- Operations are immediately executed (no flush needed)
- Best for bulk operations

```java
// Bulk insert with StatelessSession
StatelessSession session = sessionFactory.openStatelessSession();
Transaction tx = session.beginTransaction();

ScrollableResults results = session.createQuery("FROM Employee")
    .scroll(ScrollMode.FORWARD_ONLY);

while (results.next()) {
    Employee emp = (Employee) results.get(0);
    emp.setSalary(emp.getSalary() * 1.1);
    session.update(emp);
}

tx.commit();
session.close();
```

---

## Q139: What happens to First-Level Cache when session is closed?

**Answer:**

When a session is closed, the first-level cache is **completely destroyed**. All cached entities become **detached** objects.

### Lifecycle:

```java
Session session = sessionFactory.openSession();
Transaction tx = session.beginTransaction();

// Entity is in PERSISTENT state, stored in first-level cache
Employee emp = session.get(Employee.class, 1L);

tx.commit();
session.close();
// First-level cache is gone
// 'emp' is now in DETACHED state

// Accessing lazy-loaded associations throws exception
emp.getDepartment().getName(); // LazyInitializationException!
```

### Implications:

1. **Detached entities** – All managed entities become detached
2. **Lazy loading fails** – `LazyInitializationException` for uninitialized proxies
3. **No dirty checking** – Changes to detached entities are not tracked
4. **Memory freed** – All cached objects are eligible for GC

### Reattaching detached entities:

```java
// Option 1: merge() - copies state to a new managed instance
Session session2 = sessionFactory.openSession();
Transaction tx2 = session2.beginTransaction();
Employee managedEmp = (Employee) session2.merge(emp);
tx2.commit();
session2.close();

// Option 2: In JPA with Spring
@Transactional
public Employee updateEmployee(Employee detachedEmp) {
    return entityManager.merge(detachedEmp);
}
```

### Spring/JPA Context:

In Spring with `@Transactional`, the session (persistence context) lives for the duration of the transaction. With **Open Session in View (OSIV)**, it extends to the HTTP request lifecycle:

```yaml
spring:
  jpa:
    open-in-view: true  # default, keeps session open during view rendering
```

---

## Q140: Explain Second-Level Cache in Hibernate

**Answer:**

The Second-Level (L2) Cache is a **SessionFactory-scoped** cache shared across all sessions. It stores entity data (in dehydrated form) that persists beyond individual session lifecycles.

### Key Characteristics:

| Feature | First-Level Cache | Second-Level Cache |
|---------|------------------|-------------------|
| Scope | Session | SessionFactory |
| Default | Always enabled | Disabled by default |
| Shared | No (per session) | Yes (all sessions) |
| Thread-safe | No | Yes |
| Storage format | Entity objects | Dehydrated state (arrays) |
| Configuration | None needed | Requires provider & config |

### How L2 Cache stores data:

```
// Entity in L2 cache is stored as dehydrated state:
// Key: EntityClass#id
// Value: [field1_value, field2_value, field3_value, ...]

// Example: Employee#1 -> ["John", "Doe", 50000, 101]
// NOT the actual Employee object
```

### Lookup Flow:

```
session.get(Employee.class, 1L)
    │
    ▼
First-Level Cache (Session) ──── HIT? ──► Return entity
    │ MISS
    ▼
Second-Level Cache (SessionFactory) ──── HIT? ──► Assemble entity, store in L1, return
    │ MISS
    ▼
Database ──► Store in L2 (dehydrated), store in L1 (hydrated), return
```

### What can be cached in L2:

1. **Entities** – Full entity state
2. **Collections** – Associated collections (stores IDs only)
3. **Query results** – HQL/JPQL query results (via Query Cache)
4. **Natural IDs** – Natural ID to PK mappings

### Entity configuration:

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Employee {
    @Id
    @GeneratedValue
    private Long id;
    
    private String name;
    private double salary;
    
    @Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
    @OneToMany(mappedBy = "employee")
    private List<Address> addresses;
}
```

---

## Q141: How to enable and configure Second-Level Cache?

**Answer:**

### Step 1: Add dependency (e.g., EhCache)

```xml
<!-- Maven -->
<dependency>
    <groupId>org.hibernate</groupId>
    <artifactId>hibernate-ehcache</artifactId>
    <version>5.6.15.Final</version>
</dependency>

<!-- For Hibernate 6+ with JCache -->
<dependency>
    <groupId>org.hibernate.orm</groupId>
    <artifactId>hibernate-jcache</artifactId>
</dependency>
<dependency>
    <groupId>org.ehcache</groupId>
    <artifactId>ehcache</artifactId>
</dependency>
```

### Step 2: Configure in application.properties/yml

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          use_query_cache: true
          region:
            factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: org.ehcache.jsr107.EhcacheCachingProvider
            uri: classpath:ehcache.xml
```

### Step 3: Mark entities as cacheable

```java
// JPA standard annotation
@Entity
@Cacheable
@org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Product {
    @Id
    @GeneratedValue
    private Long id;
    
    private String name;
    private BigDecimal price;
    
    @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
    @OneToMany(mappedBy = "product", fetch = FetchType.LAZY)
    private List<Review> reviews;
}
```

### Step 4: Configure shared-cache-mode (optional)

```yaml
spring:
  jpa:
    properties:
      javax:
        persistence:
          sharedCache:
            mode: ENABLE_SELECTIVE  # Only cache entities with @Cacheable
            # Options: ALL, NONE, ENABLE_SELECTIVE, DISABLE_SELECTIVE
```

### Step 5: EhCache configuration (ehcache.xml)

```xml
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns="http://www.ehcache.org/v3">

    <cache-template name="default">
        <expiry>
            <ttl unit="minutes">30</ttl>
        </expiry>
        <heap unit="entries">1000</heap>
        <offheap unit="MB">10</offheap>
    </cache-template>

    <cache alias="com.example.entity.Product" uses-template="default">
        <heap unit="entries">500</heap>
    </cache>
</config>
```

---

## Q142: What are the second-level cache providers?

**Answer:**

### 1. EhCache

Best for: Single-node applications, simple setups.

```xml
<dependency>
    <groupId>org.ehcache</groupId>
    <artifactId>ehcache</artifactId>
</dependency>
<dependency>
    <groupId>org.hibernate.orm</groupId>
    <artifactId>hibernate-jcache</artifactId>
</dependency>
```

**Pros:** Simple configuration, mature, supports heap + offheap + disk tiers.  
**Cons:** Not distributed (EhCache 3 standalone), limited for clustered environments.

### 2. Hazelcast

Best for: Distributed caching, microservices.

```xml
<dependency>
    <groupId>com.hazelcast</groupId>
    <artifactId>hazelcast-hibernate53</artifactId>
    <version>5.1.0</version>
</dependency>
```

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region:
            factory_class: com.hazelcast.hibernate.HazelcastCacheRegionFactory
          # For local caching with Hazelcast:
          # factory_class: com.hazelcast.hibernate.HazelcastLocalCacheRegionFactory
```

**Pros:** Built-in clustering, auto-discovery, distributed locks.  
**Cons:** More complex setup, additional network overhead.

### 3. Infinispan

Best for: JBoss/WildFly environments, advanced distributed caching.

```xml
<dependency>
    <groupId>org.infinispan</groupId>
    <artifactId>infinispan-hibernate-cache-v60</artifactId>
</dependency>
```

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region:
            factory_class: org.infinispan.hibernate.cache.v60.InfinispanRegionFactory
        infinispan:
          cfg: infinispan-config.xml
```

**Pros:** Full replication/distribution modes, transactional support, Red Hat backed.  
**Cons:** Heavy for simple use cases.

### 4. Redis (via Redisson)

Best for: Cloud deployments, already using Redis.

```xml
<dependency>
    <groupId>org.redisson</groupId>
    <artifactId>redisson-hibernate-6</artifactId>
    <version>3.27.0</version>
</dependency>
```

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region:
            factory_class: org.redisson.hibernate.RedissonRegionFactory
        redisson:
          config: redisson-config.yaml
```

### Comparison:

| Provider | Distributed | JCache | Complexity | Performance |
|----------|-------------|--------|------------|-------------|
| EhCache | No (standalone) | Yes | Low | Very High (local) |
| Hazelcast | Yes | Yes | Medium | High |
| Infinispan | Yes | Yes | High | High |
| Redis | Yes | Via Redisson | Medium | Medium (network) |

---

## Q143: Explain @Cacheable, @Cache annotations for second-level cache

**Answer:**

### JPA `@Cacheable` annotation:

Marks an entity as eligible for second-level caching. This is the JPA standard annotation.

```java
import jakarta.persistence.Cacheable;

@Entity
@Cacheable // JPA standard - marks entity as cacheable
public class Country {
    @Id
    private String code;
    private String name;
}
```

### Hibernate `@Cache` annotation:

Specifies the caching strategy (concurrency). This is Hibernate-specific and provides more control.

```java
import org.hibernate.annotations.Cache;
import org.hibernate.annotations.CacheConcurrencyStrategy;

@Entity
@Cacheable
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "countries")
public class Country {
    @Id
    private String code;
    private String name;
    
    @Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
    @OneToMany(mappedBy = "country")
    private List<City> cities;
}
```

### `@Cache` parameters:

```java
@Cache(
    usage = CacheConcurrencyStrategy.READ_WRITE,  // Concurrency strategy
    region = "myRegion",                           // Cache region name
    include = "all"                                // "all" or "non-lazy"
)
```

### `@NaturalIdCache`:

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
@NaturalIdCache // Caches natural-id to PK resolution
public class User {
    @Id
    @GeneratedValue
    private Long id;
    
    @NaturalId
    private String email;
}

// Usage - benefits from NaturalIdCache
User user = session.byNaturalId(User.class)
    .using("email", "john@example.com")
    .load(); // Resolves email->id from cache, then entity from L2 cache
```

### JPA Cache hints in queries:

```java
// Bypass cache for a specific query
entityManager.find(Country.class, "US", 
    Map.of("jakarta.persistence.cache.retrieveMode", CacheRetrieveMode.BYPASS));

// Store result in cache
TypedQuery<Country> query = entityManager.createQuery("FROM Country", Country.class);
query.setHint("jakarta.persistence.cache.storeMode", CacheStoreMode.REFRESH);
```

---

## Q144: What are the cache concurrency strategies?

**Answer:**

Cache concurrency strategies define how concurrent access to cached entities is handled. They balance between data consistency and performance.

### 1. READ_ONLY

```java
@Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
```

- For entities that **never change** after creation
- Throws exception if you try to update
- **Best performance** – no locking overhead
- Use for: reference data, countries, lookup tables

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
public class Currency {
    @Id
    private String code;  // USD, EUR, etc.
    private String name;
    private String symbol;
}
```

### 2. NONSTRICT_READ_WRITE

```java
@Cache(usage = CacheConcurrencyStrategy.NONSTRICT_READ_WRITE)
```

- For entities that are **rarely modified**
- **No locks** – eventual consistency (stale reads possible)
- Cache is invalidated after transaction commit (small window for stale data)
- Use for: user profiles, configurations that change occasionally

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.NONSTRICT_READ_WRITE)
public class UserProfile {
    @Id
    private Long id;
    private String displayName;
    private String avatarUrl;
}
```

### 3. READ_WRITE

```java
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
```

- For entities that are **read mostly but updated sometimes**
- Uses **soft locks** to prevent stale reads during updates
- Guarantees strong consistency (no stale reads after commit)
- Higher overhead than NONSTRICT_READ_WRITE
- **Not compatible with serializable isolation**
- Use for: products, orders, most business entities

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Product {
    @Id
    @GeneratedValue
    private Long id;
    private String name;
    private BigDecimal price;
    private int stockQuantity;
}
```

### 4. TRANSACTIONAL

```java
@Cache(usage = CacheConcurrencyStrategy.TRANSACTIONAL)
```

- Full **XA transactional** guarantees
- Cache participates in the JTA transaction
- If transaction rolls back, cache changes roll back too
- Only supported by specific providers (Infinispan, EhCache with JTA)
- **Highest consistency, lowest performance**
- Use for: financial data, critical business entities

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.TRANSACTIONAL)
public class BankAccount {
    @Id
    private Long id;
    private BigDecimal balance;
}
```

### Decision Matrix:

| Strategy | Stale Reads | Locks | Performance | Use When |
|----------|-------------|-------|-------------|----------|
| READ_ONLY | No | None | Highest | Immutable data |
| NONSTRICT_READ_WRITE | Brief window | None | High | Rarely modified, stale OK |
| READ_WRITE | No | Soft locks | Medium | Frequently read, sometimes written |
| TRANSACTIONAL | No | XA | Lowest | Full ACID required on cache |

---

## Q145: What is Query Cache in Hibernate? How to enable it?

**Answer:**

The Query Cache stores the **results of queries** – specifically the list of entity IDs returned by a query along with scalar values. It works in conjunction with the second-level entity cache.

### What Query Cache stores:

```
Query: "FROM Product WHERE category = 'Electronics' AND price < 1000"
Parameters: [Electronics, 1000]

Cache Key: SQL + parameters hash
Cache Value: [productId_1, productId_2, productId_3, ...]  // Just IDs!

// When cache hit occurs:
// 1. Get IDs from query cache
// 2. For each ID, look up entity in L2 cache
// 3. If entity not in L2 cache, fetch from DB
```

### Enabling Query Cache:

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          use_query_cache: true  # Must explicitly enable
```

### Using Query Cache:

```java
// HQL with query cache
List<Product> products = session.createQuery(
        "FROM Product WHERE category = :cat", Product.class)
    .setParameter("cat", "Electronics")
    .setCacheable(true)              // Enable for this query
    .setCacheRegion("product-queries") // Optional: specific region
    .getResultList();

// Criteria API
CriteriaBuilder cb = entityManager.getCriteriaBuilder();
CriteriaQuery<Product> cq = cb.createQuery(Product.class);
Root<Product> root = cq.from(Product.class);
cq.where(cb.equal(root.get("category"), "Electronics"));

List<Product> results = entityManager.createQuery(cq)
    .setHint("org.hibernate.cacheable", true)
    .setHint("org.hibernate.cacheRegion", "product-queries")
    .getResultList();

// Spring Data JPA
@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {
    
    @QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
    List<Product> findByCategory(String category);
}
```

### Query Cache Invalidation:

The query cache is **automatically invalidated** when any entity in the queried table is inserted, updated, or deleted. This is table-level, not row-level:

```java
// This invalidates ALL query cache entries for the Product table
Product p = new Product("New Product");
session.save(p); // All cached Product queries are now stale and evicted
```

### Timestamps Cache:

Hibernate maintains a **timestamps cache** that tracks the last modification time of each table. When a query cache hit occurs, Hibernate checks if the underlying tables have been modified since the query was cached.

---

## Q146: When should you use Query Cache vs Entity Cache?

**Answer:**

### Use Entity Cache (Second-Level Cache) when:

- Entities are loaded by **primary key** frequently (`find()`, `get()`)
- Entities are referenced by many queries
- Data is read-heavy with infrequent writes
- Navigation through entity associations

```java
// Benefits from L2 entity cache
Product product = entityManager.find(Product.class, 1L);

// Association navigation benefits from collection cache
product.getReviews(); // Cached collection of IDs, each review from L2 cache
```

### Use Query Cache when:

- Same query with **same parameters** is executed frequently
- Result set is relatively **stable** (underlying table rarely changes)
- Queries against **lookup/reference** tables
- Aggregate/computed results

```java
// Good candidate for query cache - rarely changes
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Country> findAllByContinent(String continent);

// Good - category list rarely changes
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Category> findAllActive();
```

### Do NOT use Query Cache when:

```java
// BAD - table is frequently modified, cache invalidated constantly
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Order> findByStatus(OrderStatus status); // Orders change constantly

// BAD - unique parameters each time, cache never hit
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<AuditLog> findByTimestampBetween(Instant start, Instant end);
```

### Decision Guide:

| Scenario | Entity Cache | Query Cache |
|----------|-------------|-------------|
| `findById()` calls | Yes | N/A |
| Lookup tables | Yes | Yes |
| Frequently modified tables | Maybe (READ_WRITE) | No |
| Queries with varying parameters | Yes (for entities) | No |
| Same query repeated with same params | Yes (for entities) | Yes |
| Reports/aggregations | No | Maybe |

### Important Rule:

**Always enable entity cache for entities returned by cached queries.** Otherwise, the query cache returns IDs, but each ID triggers a DB fetch:

```java
// Query cache returns [1, 2, 3] but without entity cache:
// SELECT * FROM product WHERE id = 1  (N+1 problem!)
// SELECT * FROM product WHERE id = 2
// SELECT * FROM product WHERE id = 3
```

---

## Q147: How does cache invalidation work in Hibernate?

**Answer:**

### Entity Cache Invalidation:

```java
// Automatic invalidation on entity modification
@Transactional
public void updateProduct(Long id, String newName) {
    Product p = entityManager.find(Product.class, id);
    p.setName(newName);
    // On flush/commit: L2 cache entry for Product#id is updated/invalidated
}

// Delete invalidates cache
@Transactional
public void deleteProduct(Long id) {
    Product p = entityManager.find(Product.class, id);
    entityManager.remove(p);
    // L2 cache entry for Product#id is evicted
}
```

### Query Cache Invalidation:

Query cache uses **table-level timestamp tracking**. Any DML on a table invalidates ALL cached queries touching that table:

```java
// Inserting one product invalidates ALL product query cache entries
entityManager.persist(new Product("Widget"));
// Query cache for "FROM Product WHERE category='X'" -> INVALIDATED
// Query cache for "FROM Product WHERE price > 100" -> INVALIDATED
// ALL product queries invalidated!
```

### Bulk Operations bypass cache:

```java
// DANGEROUS: Bulk update bypasses cache!
entityManager.createQuery("UPDATE Product SET price = price * 1.1")
    .executeUpdate();
// L2 cache still has OLD prices!

// Solution: Manually evict after bulk ops
entityManager.getEntityManagerFactory().getCache().evict(Product.class);
```

### Manual Cache Eviction:

```java
// Evict specific entity
sessionFactory.getCache().evict(Product.class, productId);

// Evict all entities of a type
sessionFactory.getCache().evict(Product.class);

// Evict a collection
sessionFactory.getCache().evictCollectionData("Product.reviews", productId);

// Evict all query cache
sessionFactory.getCache().evictQueryRegions();

// Evict specific query region
sessionFactory.getCache().evictQueryRegion("product-queries");

// Evict everything
sessionFactory.getCache().evictAllRegions();
```

### JPA standard eviction:

```java
Cache cache = entityManager.getEntityManagerFactory().getCache();
cache.evict(Product.class, productId);  // Single entity
cache.evict(Product.class);             // All of type
cache.evictAll();                        // Everything
```

### Native SQL and Cache:

```java
// Native queries don't auto-invalidate cache!
entityManager.createNativeQuery("UPDATE products SET price = price * 1.1")
    .executeUpdate();

// Must manually synchronize:
entityManager.createNativeQuery("UPDATE products SET price = price * 1.1")
    .unwrap(org.hibernate.query.NativeQuery.class)
    .addSynchronizedEntityClass(Product.class) // Tells Hibernate to invalidate
    .executeUpdate();
```

---

## Q148: What is the difference between cache regions?

**Answer:**

Cache regions are **named segments** of the second-level cache, each with its own configuration (size, TTL, eviction policy).

### Default Region Naming:

```
Entity cache region: fully qualified class name
  e.g., "com.example.entity.Product"

Collection cache region: fully qualified class name + "." + property name
  e.g., "com.example.entity.Product.reviews"

Query cache region: "default-query-results-region" (default)
  or custom: specified via setCacheRegion()

Timestamps region: "default-update-timestamps-region"
```

### Custom Region Assignment:

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "product-cache")
public class Product { ... }

@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_ONLY, region = "reference-data")
public class Country { ... }
```

### Configuring Different Regions (EhCache):

```xml
<config xmlns="http://www.ehcache.org/v3">

    <!-- Region for reference data - large TTL, small size -->
    <cache alias="reference-data">
        <expiry>
            <ttl unit="hours">24</ttl>
        </expiry>
        <resources>
            <heap unit="entries">200</heap>
        </resources>
    </cache>

    <!-- Region for products - shorter TTL, larger size -->
    <cache alias="product-cache">
        <expiry>
            <ttl unit="minutes">15</ttl>
        </expiry>
        <resources>
            <heap unit="entries">5000</heap>
            <offheap unit="MB">50</offheap>
        </resources>
    </cache>

    <!-- Region for query results -->
    <cache alias="product-queries">
        <expiry>
            <ttl unit="minutes">5</ttl>
        </expiry>
        <resources>
            <heap unit="entries">100</heap>
        </resources>
    </cache>

    <!-- Default for any region not explicitly configured -->
    <cache-template name="default">
        <expiry>
            <ttl unit="minutes">10</ttl>
        </expiry>
        <resources>
            <heap unit="entries">1000</heap>
        </resources>
    </cache-template>
</config>
```

### Why use different regions:

1. **Different TTLs** – Reference data cached for hours, volatile data for minutes
2. **Different sizes** – More slots for frequently accessed entities
3. **Different eviction policies** – LRU for general, LFU for hot data
4. **Monitoring** – Track hit/miss rates per region
5. **Selective eviction** – Evict one region without affecting others

---

## Q149: How to configure EhCache with Spring Boot and Hibernate?

**Answer:**

### Complete Setup:

**1. Dependencies (pom.xml):**

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-cache</artifactId>
    </dependency>
    <dependency>
        <groupId>org.hibernate.orm</groupId>
        <artifactId>hibernate-jcache</artifactId>
    </dependency>
    <dependency>
        <groupId>org.ehcache</groupId>
        <artifactId>ehcache</artifactId>
        <classifier>jakarta</classifier>
    </dependency>
</dependencies>
```

**2. application.yml:**

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          use_query_cache: true
          region:
            factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: org.ehcache.jsr107.EhcacheCachingProvider
            uri: classpath:ehcache.xml
    show-sql: true
  cache:
    jcache:
      config: classpath:ehcache.xml

logging:
  level:
    org.hibernate.cache: DEBUG
    org.ehcache: DEBUG
```

**3. src/main/resources/ehcache.xml:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns="http://www.ehcache.org/v3"
        xsi:schemaLocation="http://www.ehcache.org/v3
        http://www.ehcache.org/schema/ehcache-core-3.0.xsd">

    <cache-template name="default">
        <expiry>
            <ttl unit="minutes">10</ttl>
        </expiry>
        <resources>
            <heap unit="entries">1000</heap>
            <offheap unit="MB">10</offheap>
        </resources>
    </cache-template>

    <cache alias="com.example.entity.Product" uses-template="default">
        <expiry>
            <ttl unit="minutes">30</ttl>
        </expiry>
        <resources>
            <heap unit="entries">500</heap>
        </resources>
    </cache>

    <cache alias="com.example.entity.Product.reviews" uses-template="default">
        <resources>
            <heap unit="entries">200</heap>
        </resources>
    </cache>

    <cache alias="default-query-results-region" uses-template="default">
        <expiry>
            <ttl unit="minutes">5</ttl>
        </expiry>
    </cache>

    <cache alias="default-update-timestamps-region">
        <expiry>
            <none/>
        </expiry>
        <resources>
            <heap unit="entries">5000</heap>
        </resources>
    </cache>
</config>
```

**4. Entity:**

```java
@Entity
@Cacheable
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String name;
    private BigDecimal price;
    
    @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
    @OneToMany(mappedBy = "product", fetch = FetchType.LAZY)
    private List<Review> reviews = new ArrayList<>();
}
```

**5. Repository:**

```java
@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {

    @QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
    List<Product> findByCategory(String category);
    
    @QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
    Optional<Product> findByName(String name);
}
```

**6. Enable caching in Spring Boot:**

```java
@SpringBootApplication
@EnableCaching
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

---

## Q150: What is Spring Cache abstraction? (@Cacheable, @CacheEvict, @CachePut)

**Answer:**

Spring Cache abstraction provides a **method-level caching** layer independent of the underlying cache implementation. It caches method return values based on parameters.

### Enable Spring Caching:

```java
@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public CacheManager cacheManager() {
        return new ConcurrentMapCacheManager("products", "users");
    }
}
```

### @Cacheable – Cache method results:

```java
@Service
public class ProductService {

    // Result cached with key = productId
    @Cacheable(value = "products", key = "#productId")
    public Product getProduct(Long productId) {
        // Only called on cache miss
        return productRepository.findById(productId).orElseThrow();
    }

    // Conditional caching
    @Cacheable(value = "products", key = "#name", 
               condition = "#name.length() > 3",
               unless = "#result == null")
    public Product findByName(String name) {
        return productRepository.findByName(name).orElse(null);
    }

    // Custom key generator
    @Cacheable(value = "product-search", keyGenerator = "customKeyGenerator")
    public List<Product> search(String query, Pageable pageable) {
        return productRepository.search(query, pageable);
    }
}
```

### @CacheEvict – Remove entries from cache:

```java
@Service
public class ProductService {

    // Evict single entry
    @CacheEvict(value = "products", key = "#product.id")
    public Product updateProduct(Product product) {
        return productRepository.save(product);
    }

    // Evict all entries in cache
    @CacheEvict(value = "products", allEntries = true)
    public void clearProductCache() {
    }

    // Evict before method execution
    @CacheEvict(value = "products", key = "#id", beforeInvocation = true)
    public void deleteProduct(Long id) {
        productRepository.deleteById(id);
    }
}
```

### @CachePut – Always execute and update cache:

```java
@Service
public class ProductService {

    // Always executes method AND updates cache
    @CachePut(value = "products", key = "#product.id")
    public Product saveProduct(Product product) {
        return productRepository.save(product);
    }
}
```

### @Caching – Compose multiple cache operations:

```java
@Caching(
    put = { @CachePut(value = "products", key = "#result.id") },
    evict = { 
        @CacheEvict(value = "product-search", allEntries = true),
        @CacheEvict(value = "product-categories", key = "#product.category")
    }
)
public Product createProduct(Product product) {
    return productRepository.save(product);
}
```

### @CacheConfig – Class-level defaults:

```java
@Service
@CacheConfig(cacheNames = "products")
public class ProductService {
    
    @Cacheable(key = "#id")
    public Product get(Long id) { ... }
    
    @CacheEvict(key = "#id")
    public void delete(Long id) { ... }
}
```

### Using with EhCache/Redis:

```java
@Configuration
@EnableCaching
public class RedisCacheConfig {
    
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .serializeKeysWith(RedisSerializationContext.SerializationPair
                .fromSerializer(new StringRedisSerializer()))
            .serializeValuesWith(RedisSerializationContext.SerializationPair
                .fromSerializer(new GenericJackson2JsonRedisSerializer()));

        return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(config)
            .withCacheConfiguration("products",
                RedisCacheConfiguration.defaultCacheConfig().entryTtl(Duration.ofHours(1)))
            .build();
    }
}
```

---

## Q151: How to integrate Spring Cache with Hibernate second-level cache?

**Answer:**

Spring Cache and Hibernate L2 Cache are **different layers** that can complement each other:

- **Hibernate L2 Cache** – Entity/query level, managed by Hibernate automatically
- **Spring Cache** – Method/service level, managed by Spring AOP

### Architecture:

```
Controller → Service (@Cacheable) → Repository → Hibernate L2 Cache → Database
                ↓                                       ↓
         Spring Cache                           Hibernate Cache
      (method results)                         (entities/queries)
```

### Shared Cache Provider (both using same EhCache):

```java
@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    public JCacheCacheManager cacheManager(javax.cache.CacheManager jCacheManager) {
        return new JCacheCacheManager(jCacheManager);
    }

    @Bean
    public javax.cache.CacheManager jCacheManager() {
        // Same EhCache instance used by Hibernate and Spring
        CachingProvider provider = Caching.getCachingProvider(
            "org.ehcache.jsr107.EhcacheCachingProvider");
        return provider.getCacheManager(
            getClass().getResource("/ehcache.xml").toURI(),
            getClass().getClassLoader());
    }
}
```

### Using both layers effectively:

```java
@Service
public class ProductService {

    @Autowired
    private ProductRepository productRepository;

    // Spring Cache: caches the DTO transformation result
    @Cacheable(value = "product-dtos", key = "#id")
    public ProductDTO getProductDTO(Long id) {
        // Hibernate L2 cache: caches the entity itself
        Product product = productRepository.findById(id).orElseThrow();
        return mapToDTO(product); // DTO conversion cached by Spring
    }

    // Spring Cache: caches computed/aggregated results
    @Cacheable(value = "category-stats")
    public CategoryStats getCategoryStatistics(String category) {
        // Complex computation cached at service level
        List<Product> products = productRepository.findByCategory(category);
        return computeStats(products);
    }

    @Caching(evict = {
        @CacheEvict(value = "product-dtos", key = "#product.id"),
        @CacheEvict(value = "category-stats", key = "#product.category")
    })
    @Transactional
    public Product updateProduct(Product product) {
        // Hibernate L2 cache auto-updated on entity save
        return productRepository.save(product);
    }
}
```

### When to use which:

| Scenario | Spring Cache | Hibernate L2 Cache |
|----------|-------------|-------------------|
| DTO transformations | Yes | No |
| Entity by ID lookups | Optional | Yes |
| Complex aggregations | Yes | No |
| External API calls | Yes | No |
| Entity associations | No | Yes |
| Query results | Optional | Yes (Query Cache) |

---

## Q152: What are cache eviction policies (LRU, LFU, FIFO)?

**Answer:**

Eviction policies determine which entries to remove when the cache reaches capacity.

### 1. LRU (Least Recently Used)

Evicts the entry that hasn't been **accessed** for the longest time.

```
Access pattern: A, B, C, D, A, B, E (cache size = 4)
State after E: [A, B, D, E] → C evicted (least recently used)
```

**Best for:** General-purpose, most common choice. Works well when recent access predicts future access.

### 2. LFU (Least Frequently Used)

Evicts the entry with the **fewest accesses** over time.

```
Access pattern: A(10x), B(5x), C(2x), D(1x) → capacity reached
New entry E: evict D (frequency = 1, lowest)
```

**Best for:** Keeping "hot" items in cache. Works well when popularity is stable.  
**Downside:** Previously popular items can get stuck in cache even if no longer needed.

### 3. FIFO (First In, First Out)

Evicts the **oldest** entry regardless of access pattern.

```
Insert order: A, B, C, D → capacity reached
New entry E: evict A (first inserted)
```

**Best for:** Time-sensitive data where age determines relevance.

### 4. TTL (Time To Live)

Entry expires after a **fixed duration** since creation.

### 5. TTI (Time To Idle)

Entry expires after a fixed duration since **last access**.

### Configuring in EhCache:

```xml
<cache alias="products">
    <expiry>
        <ttl unit="minutes">30</ttl>  <!-- TTL-based expiry -->
    </expiry>
    <resources>
        <!-- EhCache 3 uses LRU by default for heap tier -->
        <heap unit="entries">1000</heap>
        <offheap unit="MB">50</offheap>
        <disk unit="GB">1</disk>
    </resources>
</cache>
```

### Configuring in Caffeine (Spring Cache):

```java
@Bean
public CacheManager cacheManager() {
    CaffeineCacheManager manager = new CaffeineCacheManager();
    manager.setCaffeine(Caffeine.newBuilder()
        .maximumSize(10_000)           // LRU eviction when size exceeded
        .expireAfterWrite(Duration.ofMinutes(30))  // TTL
        .expireAfterAccess(Duration.ofMinutes(10)) // TTI
        .recordStats());                // Enable statistics
    return manager;
}
```

### Configuring in Redis:

```java
@Bean
public CacheManager cacheManager(RedisConnectionFactory factory) {
    RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
        .entryTtl(Duration.ofMinutes(30)); // TTL (Redis uses LRU by default when maxmemory reached)
    
    return RedisCacheManager.builder(factory)
        .cacheDefaults(config)
        .build();
}
```

Redis eviction policies (configured in redis.conf):
- `allkeys-lru` – LRU among all keys
- `volatile-lru` – LRU among keys with TTL set
- `allkeys-lfu` – LFU among all keys
- `noeviction` – Return errors when memory full

---

## Q153: How to handle cache in distributed systems?

**Answer:**

In distributed systems, caching introduces **consistency challenges** because multiple nodes may have their own cache copies.

### Challenges:

1. **Cache coherence** – Different nodes may have different versions
2. **Invalidation propagation** – How to notify all nodes of changes
3. **Network partition** – What happens when nodes can't communicate
4. **Thundering herd** – All caches expire simultaneously

### Strategy 1: Distributed Cache (Shared)

All nodes share a single remote cache:

```java
// Redis as shared cache
@Configuration
@EnableCaching
public class DistributedCacheConfig {
    
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory factory) {
        return RedisCacheManager.builder(factory)
            .cacheDefaults(RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(15)))
            .build();
    }
}
```

**Pros:** Strong consistency, single source of truth.  
**Cons:** Network latency for every cache access, single point of failure.

### Strategy 2: Near Cache (Local + Remote)

Local cache backed by distributed cache:

```java
// Hazelcast near-cache configuration
@Bean
public Config hazelcastConfig() {
    Config config = new Config();
    
    NearCacheConfig nearCacheConfig = new NearCacheConfig()
        .setName("products")
        .setInMemoryFormat(InMemoryFormat.OBJECT)
        .setMaxIdleSeconds(300)
        .setTimeToLiveSeconds(600)
        .setEvictionConfig(new EvictionConfig()
            .setMaxSizePolicy(MaxSizePolicy.ENTRY_COUNT)
            .setSize(1000)
            .setEvictionPolicy(EvictionPolicy.LRU));
    
    config.getMapConfig("products")
        .setNearCacheConfig(nearCacheConfig);
    
    return config;
}
```

### Strategy 3: Cache-Aside with Pub/Sub Invalidation

```java
@Service
public class ProductService {
    
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    
    @Autowired
    private LocalCacheManager localCache;
    
    public Product getProduct(Long id) {
        // Check local cache
        Product cached = localCache.get("product:" + id);
        if (cached != null) return cached;
        
        // Check Redis
        cached = (Product) redisTemplate.opsForValue().get("product:" + id);
        if (cached != null) {
            localCache.put("product:" + id, cached);
            return cached;
        }
        
        // DB fetch
        Product product = productRepository.findById(id).orElseThrow();
        redisTemplate.opsForValue().set("product:" + id, product, Duration.ofMinutes(30));
        localCache.put("product:" + id, product);
        return product;
    }
    
    @Transactional
    public Product updateProduct(Product product) {
        Product saved = productRepository.save(product);
        
        // Invalidate Redis
        redisTemplate.delete("product:" + product.getId());
        
        // Publish invalidation event to all nodes
        redisTemplate.convertAndSend("cache-invalidation", 
            new CacheInvalidationEvent("product", product.getId()));
        
        return saved;
    }
    
    // Listener on all nodes
    @RedisListener(topics = "cache-invalidation")
    public void onCacheInvalidation(CacheInvalidationEvent event) {
        localCache.evict(event.getType() + ":" + event.getId());
    }
}
```

### Strategy 4: Write-Through / Write-Behind

```java
// Write-through: update cache and DB synchronously
@CachePut(value = "products", key = "#product.id")
@Transactional
public Product saveProduct(Product product) {
    return productRepository.save(product); // DB + cache updated together
}

// Write-behind: update cache immediately, DB asynchronously (Hazelcast MapStore)
public class ProductMapStore implements MapStore<Long, Product> {
    @Override
    public void store(Long key, Product value) {
        productRepository.save(value); // Called asynchronously
    }
}
```

### Hibernate L2 Cache in Distributed Setup:

```yaml
# Using Hazelcast as Hibernate L2 cache provider
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region:
            factory_class: com.hazelcast.hibernate.HazelcastCacheRegionFactory
          hazelcast:
            use_native_client: true
            native_client_address: hazelcast-cluster:5701
```

---

## Q154: What are cache-related performance pitfalls?

**Answer:**

### 1. N+1 with Query Cache but no Entity Cache

```java
// Query cache returns IDs [1, 2, 3, ..., 100]
// Without entity cache → 100 individual SELECT statements!
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Product> findByCategory(String category);

// FIX: Always cache entities too
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Product { ... }
```

### 2. Cache Thrashing on Frequently Modified Tables

```java
// Query cache on volatile table: constantly invalidated
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Order> findRecentOrders(); // BAD - orders table changes constantly

// Every INSERT/UPDATE/DELETE on orders table invalidates ALL order query caches
```

### 3. Memory Overflow from Unbounded First-Level Cache

```java
// BAD: Loading millions of entities in single session
@Transactional
public void processAll() {
    List<Record> records = recordRepository.findAll(); // 1M records in memory!
}

// FIX: Stream with periodic clear
@Transactional(readOnly = true)
public void processAll() {
    try (Stream<Record> stream = recordRepository.streamAll()) {
        stream.forEach(record -> {
            process(record);
            entityManager.detach(record);
        });
    }
}
```

### 4. Caching Large Collections

```java
// BAD: Caching a collection with thousands of entries
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
@OneToMany(mappedBy = "department")
private List<Employee> employees; // 10,000 employees cached as IDs

// Adding ONE employee invalidates entire collection cache
// Then ALL 10,000 IDs must be re-fetched
```

### 5. Stale Data after Bulk/Native Operations

```java
// Cache is stale after native SQL
entityManager.createNativeQuery("UPDATE products SET active = false WHERE stock = 0")
    .executeUpdate();
// L2 cache still shows active = true!

// FIX:
sessionFactory.getCache().evict(Product.class);
```

### 6. Serialization Overhead in Distributed Cache

```java
// Large entity graphs serialized to Redis = slow
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Order {
    @OneToMany(cascade = CascadeType.ALL, fetch = FetchType.EAGER)
    private List<OrderItem> items; // All serialized together = large payload
}

// FIX: Cache entities separately, use LAZY loading
```

### 7. Thundering Herd / Cache Stampede

```java
// Popular item's cache expires → 1000 concurrent requests all hit DB simultaneously

// FIX: Use cache locking / "probabilistic early expiration"
@Cacheable(value = "products", key = "#id", sync = true) // sync prevents stampede
public Product getProduct(Long id) {
    return productRepository.findById(id).orElseThrow();
}
```

### 8. Wrong Concurrency Strategy

```java
// Using READ_ONLY on mutable entity → exception on update
@Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
public class Product { ... } // Throws if you update!

// Using TRANSACTIONAL without JTA → doesn't work
@Cache(usage = CacheConcurrencyStrategy.TRANSACTIONAL) // Needs JTA transaction manager
```

---

## Q155: How to monitor and debug Hibernate cache?

**Answer:**

### 1. Hibernate Statistics:

```yaml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
```

```java
@Component
public class CacheMonitor {

    @Autowired
    private EntityManagerFactory emf;

    public void printStats() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        
        System.out.println("=== Second Level Cache ===");
        System.out.println("Hit count: " + stats.getSecondLevelCacheHitCount());
        System.out.println("Miss count: " + stats.getSecondLevelCacheMissCount());
        System.out.println("Put count: " + stats.getSecondLevelCachePutCount());
        
        double hitRatio = (double) stats.getSecondLevelCacheHitCount() /
            (stats.getSecondLevelCacheHitCount() + stats.getSecondLevelCacheMissCount());
        System.out.println("Hit ratio: " + hitRatio);
        
        System.out.println("\n=== Query Cache ===");
        System.out.println("Hit count: " + stats.getQueryCacheHitCount());
        System.out.println("Miss count: " + stats.getQueryCacheMissCount());
        
        // Per-region stats
        for (String region : stats.getSecondLevelCacheRegionNames()) {
            CacheRegionStatistics regionStats = stats.getCacheRegionStatistics(region);
            System.out.println("Region: " + region);
            System.out.println("  Hits: " + regionStats.getHitCount());
            System.out.println("  Misses: " + regionStats.getMissCount());
            System.out.println("  Puts: " + regionStats.getPutCount());
            System.out.println("  Elements in memory: " + regionStats.getElementCountInMemory());
        }
    }
}
```

### 2. Expose via Actuator/JMX:

```java
@RestController
@RequestMapping("/admin/cache")
public class CacheAdminController {

    @Autowired
    private EntityManagerFactory emf;
    
    @GetMapping("/stats")
    public Map<String, Object> getCacheStats() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        return Map.of(
            "l2CacheHits", stats.getSecondLevelCacheHitCount(),
            "l2CacheMisses", stats.getSecondLevelCacheMissCount(),
            "queryCacheHits", stats.getQueryCacheHitCount(),
            "queryCacheMisses", stats.getQueryCacheMissCount()
        );
    }
    
    @PostMapping("/evict/{region}")
    public void evictRegion(@PathVariable String region) {
        emf.unwrap(SessionFactory.class).getCache().evictQueryRegion(region);
    }
    
    @PostMapping("/evict-all")
    public void evictAll() {
        emf.unwrap(SessionFactory.class).getCache().evictAllRegions();
    }
}
```

### 3. Micrometer Integration:

```java
@Configuration
public class HibernateCacheMetrics {

    @Bean
    public MeterBinder hibernateStatistics(EntityManagerFactory emf) {
        return new HibernateMetrics(
            emf.unwrap(SessionFactory.class), "hibernate", Collections.emptyList());
    }
}

// Or with Spring Boot auto-configuration:
// spring.jpa.properties.hibernate.generate_statistics=true
// Metrics automatically exposed: hibernate.second.level.cache.hits, etc.
```

### 4. Logging Configuration:

```yaml
logging:
  level:
    # Hibernate cache operations
    org.hibernate.cache: DEBUG
    
    # See what's stored/retrieved
    org.hibernate.cache.spi.access: TRACE
    
    # EhCache internals
    org.ehcache: DEBUG
    net.sf.ehcache: DEBUG
    
    # See SQL queries (verify cache hits avoid SQL)
    org.hibernate.SQL: DEBUG
    org.hibernate.type.descriptor.sql: TRACE
```

### 5. Checking if entity is in cache:

```java
// Check programmatically
Cache cache = entityManager.getEntityManagerFactory().getCache();
boolean isCached = cache.contains(Product.class, productId);
System.out.println("Product " + productId + " in cache: " + isCached);
```

### 6. Spring Boot Actuator for Spring Cache:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: caches, metrics
```

```
GET /actuator/caches          → List all cache managers and caches
GET /actuator/metrics/cache.gets → Cache hit/miss metrics
DELETE /actuator/caches/{name} → Evict specific cache
```

### 7. Debug Checklist:

1. Enable `hibernate.generate_statistics=true`
2. Check hit ratio – should be > 80% for effectiveness
3. Monitor cache size vs. configured maximum
4. Watch for high put counts with low hit counts (cache thrashing)
5. Compare query count with/without cache
6. Verify no `SELECT` SQL when cache should be serving data
