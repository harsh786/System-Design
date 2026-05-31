# Memory Management & Persistence Context Internals (Staff Engineer / Architect Level)

> Understanding how Hibernate uses memory is critical for preventing OutOfMemoryError, optimizing GC behavior, and designing systems that handle large datasets. This document covers internal memory structures, monitoring, and production patterns.

---

## 1. Persistence Context Memory Model

### What Hibernate Stores Per Managed Entity

```
┌─────────────────────────────────────────────────────────────────────┐
│  MEMORY LAYOUT PER MANAGED ENTITY                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────┐                                    │
│  │ Entity Instance             │  ~100-500 bytes (your object)      │
│  │ ├─ id: Long                 │  16 bytes (boxed)                  │
│  │ ├─ name: String             │  40+ bytes (object header + chars) │
│  │ ├─ email: String            │  40+ bytes                         │
│  │ ├─ age: Integer             │  16 bytes (boxed)                  │
│  │ └─ address: Address         │  ~100 bytes (embedded)             │
│  └─────────────────────────────┘                                    │
│                                                                       │
│  ┌─────────────────────────────┐                                    │
│  │ EntityEntry                 │  ~120 bytes                        │
│  │ ├─ status: Status           │  enum ref (8 bytes)                │
│  │ ├─ loadedState: Object[]    │  40 + N×8 bytes (SNAPSHOT!)       │
│  │ │   [0] "John"  ←────────────── copy of name at load time       │
│  │ │   [1] "john@..."  ←────────── copy of email at load time      │
│  │ │   [2] 30  ←────────────────── copy of age at load time        │
│  │ │   [3] Address{...}  ←──────── copy of address at load time    │
│  │ ├─ persister: ref           │  8 bytes                           │
│  │ ├─ version: Object          │  16 bytes                          │
│  │ ├─ lockMode: LockMode       │  8 bytes                           │
│  │ └─ existsInDatabase: bool   │  1 byte (+ padding)               │
│  └─────────────────────────────┘                                    │
│                                                                       │
│  ┌─────────────────────────────┐                                    │
│  │ EntityKey (in HashMap)      │  ~80 bytes                         │
│  │ ├─ identifier: Object       │  8-16 bytes                        │
│  │ ├─ persister: ref           │  8 bytes                           │
│  │ └─ hashCode: int            │  4 bytes                           │
│  └─────────────────────────────┘                                    │
│                                                                       │
│  ┌─────────────────────────────┐                                    │
│  │ HashMap.Entry (x2)          │  ~64 bytes (two maps)             │
│  │ ├─ entitiesByKey entry      │  32 bytes                          │
│  │ └─ entityEntryContext entry  │  32 bytes                          │
│  └─────────────────────────────┘                                    │
│                                                                       │
│  ┌─────────────────────────────┐                                    │
│  │ Per Collection (if any)     │  ~200-500 bytes per collection    │
│  │ ├─ PersistentList/Set       │  wrapper object                    │
│  │ ├─ CollectionEntry          │  snapshot of collection state      │
│  │ ├─ CollectionKey            │  in collections map                │
│  │ └─ Collection elements      │  actual child entities (recurse!)  │
│  └─────────────────────────────┘                                    │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│ TOTAL OVERHEAD per entity (excluding entity data itself):            │
│                                                                       │
│   5 fields:   ~500-800 bytes overhead                               │
│   10 fields:  ~800-1200 bytes overhead                              │
│   20 fields:  ~1200-2000 bytes overhead                             │
│   + collections: +300-500 bytes per collection                       │
│                                                                       │
│ NOTE: The SNAPSHOT (loadedState) roughly DOUBLES the memory          │
│       of the entity's persistent fields!                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Memory Calculation Examples

```
Example 1: Simple entity (User with 5 fields)
─────────────────────────────────────────────
Entity instance:        ~200 bytes
EntityEntry + snapshot: ~300 bytes
EntityKey + map entries: ~150 bytes
─────────────────────────────────────────────
Total per entity:       ~650 bytes

10,000 users loaded:    ~6.5 MB
100,000 users loaded:   ~65 MB  ← DANGER in single session!

Example 2: Order with 10 items (aggregate)
─────────────────────────────────────────────
Order entity:           ~400 bytes
Order EntityEntry:      ~500 bytes (more fields)
Order maps overhead:    ~150 bytes
PersistentList wrapper: ~200 bytes
CollectionEntry:        ~150 bytes
10 OrderItem entities:  10 × 650 = ~6,500 bytes
─────────────────────────────────────────────
Total per Order:        ~7,900 bytes (~8 KB)

1,000 Orders loaded:    ~8 MB
10,000 Orders loaded:   ~80 MB  ← in a single session!

Example 3: Large entity with @Lob
─────────────────────────────────────────────
Entity with 1MB JSON blob in a field:
Entity instance:        ~1,000,200 bytes  (1MB data)
Snapshot (loadedState): ~1,000,200 bytes  (ANOTHER 1MB copy!)
─────────────────────────────────────────────
Total per entity:       ~2 MB  (data stored TWICE!)

100 such entities:      ~200 MB
```

### The Snapshot Problem

```java
// WHY does Hibernate keep a snapshot?
// For DIRTY CHECKING: comparing current state vs loaded state

// Entity loaded:
User user = em.find(User.class, 1L);  
// Hibernate stores: loadedState = {"John", "john@x.com", 30}

// User modifies:
user.setName("Jane");

// At flush time, Hibernate compares:
// currentState = {"Jane", "john@x.com", 30}
// loadedState  = {"John", "john@x.com", 30}  ← the snapshot
// Diff: field[0] changed → generate UPDATE SET name='Jane' WHERE id=1

// COST: Every String, every collection, every embedded object
// has TWO copies in memory: the live entity + the snapshot
```

---

## 2. Session Size Monitoring & Diagnostics

### Measuring Session Size

```java
@Service
public class SessionDiagnosticsService {
    
    @PersistenceContext
    private EntityManager entityManager;
    
    public SessionStats getSessionStats() {
        Session session = entityManager.unwrap(Session.class);
        SessionStatistics stats = session.getStatistics();
        
        return new SessionStats(
            stats.getEntityCount(),       // Number of managed entities
            stats.getCollectionCount(),   // Number of managed collections
            stats.getEntityKeys()         // Set of EntityKey objects
        );
    }
}

// Usage in request interceptor:
@Component
public class SessionSizeInterceptor implements HandlerInterceptor {
    
    @PersistenceContext
    private EntityManager em;
    
    private static final int WARN_THRESHOLD = 500;
    private static final int ERROR_THRESHOLD = 5000;
    
    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        Session session = em.unwrap(Session.class);
        SessionStatistics stats = session.getStatistics();
        int entityCount = stats.getEntityCount();
        
        if (entityCount > ERROR_THRESHOLD) {
            log.error("Session bloat detected! {} entities in session for {} {}",
                entityCount, request.getMethod(), request.getRequestURI());
        } else if (entityCount > WARN_THRESHOLD) {
            log.warn("Large session: {} entities for {} {}",
                entityCount, request.getMethod(), request.getRequestURI());
        }
    }
}
```

### Micrometer Integration for Session Metrics

```java
@Configuration
public class HibernateSessionMetrics {
    
    @Bean
    public MeterBinder sessionMetrics(EntityManagerFactory emf) {
        return registry -> {
            SessionFactory sf = emf.unwrap(SessionFactory.class);
            Statistics stats = sf.getStatistics();
            
            Gauge.builder("hibernate.sessions.open", stats, Statistics::getSessionOpenCount)
                .register(registry);
            Gauge.builder("hibernate.sessions.close", stats, Statistics::getSessionCloseCount)
                .register(registry);
            Gauge.builder("hibernate.entities.load", stats, Statistics::getEntityLoadCount)
                .register(registry);
            Gauge.builder("hibernate.entities.insert", stats, Statistics::getEntityInsertCount)
                .register(registry);
            Gauge.builder("hibernate.entities.fetch", stats, Statistics::getEntityFetchCount)
                .register(registry);
            Gauge.builder("hibernate.collections.load", stats, Statistics::getCollectionLoadCount)
                .register(registry);
        };
    }
}
```

### Common Causes of Session Bloat

```
1. MISSING PAGINATION
─────────────────────
// WRONG: loads entire table
List<User> users = userRepository.findAll();  // 1M users → OOM

// RIGHT: always paginate
Page<User> users = userRepository.findAll(PageRequest.of(0, 50));

2. CASCADING LOADS (N+1 escalation)
─────────────────────────────────────
// Load 100 orders, each eagerly loads 20 items + customer + address
// = 100 + 100×20 + 100 + 100 = 2,300 entities in session!

3. LONG-RUNNING TRANSACTIONS
─────────────────────────────
// Transaction processing 10,000 records one by one
// Each record loaded → accumulates in session
@Transactional
public void processAll() {
    for (Long id : allIds) {  // 10,000 IDs
        Entity e = repository.findById(id).get();  // +1 entity per iteration
        process(e);
        // After 10,000 iterations: 10,000 entities in session!
    }
}

4. OPEN SESSION IN VIEW (OSIV)
─────────────────────────────────
// Session spans entire HTTP request
// Controller → Service → Repository all share same session
// Every lazy load adds to the same growing session
// Response serialization triggers more lazy loads
```

---

## 3. Large Batch Processing Patterns

### Pattern 1: Flush-Clear Batching

```java
@Service
public class BatchInsertService {
    
    @PersistenceContext
    private EntityManager em;
    
    @Transactional
    public void insertLargeDataset(List<DataRecord> records) {
        int batchSize = 50;  // Match hibernate.jdbc.batch_size
        
        for (int i = 0; i < records.size(); i++) {
            em.persist(mapToEntity(records.get(i)));
            
            if ((i + 1) % batchSize == 0) {
                em.flush();   // Execute pending INSERTs (batch of 50)
                em.clear();   // Detach all entities → free memory!
            }
        }
        // Flush remaining
        em.flush();
        em.clear();
    }
}

// Memory profile:
// Without flush/clear: entities accumulate → O(N) memory
// With flush/clear:    constant ~50 entities → O(1) memory
//
// Time (items processed) → Memory
// ─────────────────────────────────────
// Without:  ■■■■■■■■■■■■■■■■■■■■■■■■ (linear growth, OOM at ~500K)
// With:     ■■■■■■ (constant ~5MB regardless of dataset size)
```

**Configuration for batching:**
```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 50
          batch_versioned_data: true
        order_inserts: true    # Group inserts by entity type
        order_updates: true    # Group updates by entity type
```

**Caveat with clear():**
```java
// After em.clear(), all previously loaded entities are DETACHED
// Any reference you hold becomes detached → LazyInitializationException

Order order = em.find(Order.class, 1L);
em.clear();
order.getItems().size();  // LazyInitializationException!

// Solution: don't hold references across clear() boundaries
```

### Pattern 2: StatelessSession

```java
@Service
public class BulkImportService {
    
    @Autowired
    private SessionFactory sessionFactory;
    
    public void importMillionRecords(Iterator<DataRecord> records) {
        StatelessSession session = sessionFactory.openStatelessSession();
        Transaction tx = session.beginTransaction();
        
        try {
            int count = 0;
            while (records.hasNext()) {
                ProductEntity entity = mapToEntity(records.next());
                session.insert(entity);  // Direct INSERT, no PC storage
                
                count++;
                if (count % 1000 == 0) {
                    // No flush needed - StatelessSession doesn't batch
                    // But we can commit periodically for large datasets
                    tx.commit();
                    tx = session.beginTransaction();
                }
            }
            tx.commit();
        } catch (Exception e) {
            tx.rollback();
            throw e;
        } finally {
            session.close();
        }
    }
}
```

**StatelessSession characteristics:**
```
┌─────────────────────────────────────────────────────────────┐
│ StatelessSession vs Session                                  │
├──────────────────────┬──────────────────────────────────────┤
│ Feature              │ Session           │ StatelessSession  │
├──────────────────────┼───────────────────┼──────────────────┤
│ Persistence Context  │ Yes               │ NO               │
│ First-Level Cache    │ Yes               │ NO               │
│ Dirty Checking       │ Yes (automatic)   │ NO               │
│ Cascading            │ Yes               │ NO               │
│ Collections handling │ Yes (lazy/eager)  │ NO               │
│ Interceptors/Events  │ Yes               │ NO               │
│ Second-Level Cache   │ Yes (read/write)  │ NO               │
│ Write-behind         │ Yes (batch)       │ NO (immediate)   │
│ Memory per entity    │ ~1KB overhead     │ ~0 overhead      │
│ Identity guarantee   │ Yes               │ NO               │
├──────────────────────┼───────────────────┼──────────────────┤
│ Use case             │ Normal CRUD       │ Bulk operations  │
│                      │ Business logic    │ ETL/migration    │
│                      │ Complex graphs    │ High throughput  │
└──────────────────────┴───────────────────┴──────────────────┘
```

### Pattern 3: ScrollableResults (Database Cursor)

```java
@Service
public class LargeExportService {
    
    @PersistenceContext
    private EntityManager em;
    
    @Transactional(readOnly = true)
    public void exportAllUsers(OutputStream output) {
        Session session = em.unwrap(Session.class);
        
        ScrollableResults<User> scroll = session
            .createQuery("FROM User u ORDER BY u.id", User.class)
            .setFetchSize(100)       // Database cursor fetch size
            .setReadOnly(true)       // No dirty checking
            .scroll(ScrollMode.FORWARD_ONLY);
        
        try {
            int count = 0;
            while (scroll.next()) {
                User user = scroll.get();
                writeToOutput(output, user);
                
                session.evict(user);  // Remove from PC immediately
                count++;
                
                if (count % 1000 == 0) {
                    session.clear();  // Safety: clear any accumulated references
                }
            }
        } finally {
            scroll.close();
        }
    }
}

// Memory profile with ScrollableResults + evict:
// Constant memory regardless of total result set size
// Only fetchSize entities in memory at any time
// Database holds the cursor (server-side)
```

**Database cursor behavior:**
```
PostgreSQL: TRUE server-side cursor (memory on DB side)
  - Requires: autocommit=false (inside transaction)
  - fetchSize > 0 activates cursor
  
MySQL: BY DEFAULT loads entire ResultSet into client memory!
  - To get streaming: setFetchSize(Integer.MIN_VALUE)
  - Or use: useCursorFetch=true&defaultFetchSize=100 in URL
  - Critical difference from PostgreSQL!
```

### Pattern 4: Stream API (JPA 2.2+)

```java
public interface UserRepository extends JpaRepository<User, Long> {
    
    @QueryHints(@QueryHint(name = HINT_FETCH_SIZE, value = "100"))
    @Query("SELECT u FROM User u")
    Stream<User> streamAll();
}

@Service
public class UserExportService {
    
    @Transactional(readOnly = true)  // REQUIRED for streaming
    public void exportUsers(Writer writer) {
        try (Stream<User> stream = userRepository.streamAll()) {
            stream.forEach(user -> {
                writeUser(writer, user);
                entityManager.detach(user);  // Free memory
            });
        }
        // Stream auto-closed, cursor released
    }
}
```

**Comparison of approaches:**
```
┌──────────────────────────────────────────────────────────────────┐
│ Memory Usage Comparison: Processing 1,000,000 Records            │
├────────────────────┬──────────────────┬─────────────────────────┤
│ Approach           │ Peak Memory      │ Notes                    │
├────────────────────┼──────────────────┼─────────────────────────┤
│ findAll()          │ ~2 GB (OOM)      │ All in memory            │
│ Pagination (1000)  │ ~10 MB           │ 1000 at a time          │
│ Flush/Clear (50)   │ ~5 MB            │ For writes              │
│ ScrollableResults  │ ~2 MB            │ Server cursor            │
│ Stream + detach    │ ~2 MB            │ Clean API               │
│ StatelessSession   │ ~500 KB          │ Zero PC overhead         │
│ Raw JDBC           │ ~200 KB          │ Minimal overhead         │
└────────────────────┴──────────────────┴─────────────────────────┘
```

### Pattern 5: Spring Batch with JPA

```java
@Configuration
public class BatchJobConfig {
    
    @Bean
    public JpaPagingItemReader<Order> orderReader(EntityManagerFactory emf) {
        return new JpaPagingItemReaderBuilder<Order>()
            .name("orderReader")
            .entityManagerFactory(emf)
            .queryString("SELECT o FROM Order o WHERE o.status = 'PENDING'")
            .pageSize(100)  // Reads 100 records per page
            .build();
        // JpaPagingItemReader: new EntityManager per page → no session bloat
    }
    
    @Bean
    public ItemProcessor<Order, Order> orderProcessor() {
        return order -> {
            order.setStatus(OrderStatus.PROCESSED);
            return order;
        };
    }
    
    @Bean
    public JpaItemWriter<Order> orderWriter(EntityManagerFactory emf) {
        JpaItemWriter<Order> writer = new JpaItemWriter<>();
        writer.setEntityManagerFactory(emf);
        return writer;
        // Writes chunk, then EntityManager is cleared
    }
    
    @Bean
    public Step processOrdersStep(JobRepository jobRepository,
                                   PlatformTransactionManager txManager) {
        return new StepBuilder("processOrders", jobRepository)
            .<Order, Order>chunk(100, txManager)  // 100 items per chunk
            .reader(orderReader(null))
            .processor(orderProcessor())
            .writer(orderWriter(null))
            .build();
        // Each chunk: read 100 → process → write → commit → clear EM
        // Memory: constant ~100 entities regardless of total dataset
    }
}
```

---

## 4. Garbage Collection Impact

### How Managed Entities Prevent GC

```
┌─────────────────────────────────────────────────────────────────┐
│ GC ROOT CHAIN (why managed entities can't be collected)          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Thread Stack                                                    │
│    └─ EntityManager (local variable or thread-bound)            │
│         └─ SessionImpl                                           │
│              └─ StatefulPersistenceContext                       │
│                   └─ entitiesByKey: HashMap                      │
│                        └─ Entry[0]: EntityKey → User("John")    │
│                        └─ Entry[1]: EntityKey → User("Jane")    │
│                        └─ Entry[2]: EntityKey → Order(...)      │
│                        └─ ... (ALL managed entities)            │
│                                                                   │
│  STRONG REFERENCE CHAIN → GC CANNOT collect any managed entity │
│                                                                   │
│  Only when:                                                      │
│  - em.clear() → removes all entities from maps                  │
│  - em.detach(entity) → removes one entity from maps            │
│  - em.close() → session closed, all references released         │
│  - Transaction commit/rollback + session close (typical)        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### GC Patterns with Large Sessions

```
Scenario: Processing 100,000 entities without clearing session

JVM Heap: 2 GB
Session accumulating entities over time:

Time ──────────────────────────────────────────────────→

Heap Usage:
2GB ┤                                            ╱OOM!
    │                                          ╱
    │                                        ╱
    │                                      ╱
    │                                    ╱ (GC can't help -
    │                    ╱─────────────╱    all objects reachable)
    │                  ╱ 
    │                ╱ Full GC
    │    ╱─────────╱   (long pause, but 
    │  ╱               nothing to free!)
    │╱
    ├──────────────────────────────────────────────────→
    0                                              Time

GC Log Pattern:
[GC (Allocation Failure) 1800M→1750M(2048M), 0.3s]  ← Only freed 50MB!
[Full GC (Ergonomics) 1900M→1890M(2048M), 5.2s]     ← Long pause, barely freed anything
[OutOfMemoryError: Java heap space]                   ← Game over

WITH flush/clear every 50 entities:

2GB ┤
    │
    │
    │
    │      ╱╲   ╱╲   ╱╲   ╱╲   ╱╲   ╱╲   (sawtooth - healthy)
    │    ╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
    │  ╱  Minor GC cleans up detached entities
200M├╱─────────────────────────────────────────────────
    ├──────────────────────────────────────────────────→
    0                                              Time
```

### Tuning Strategy

```
Rules of thumb:
1. Keep transactions SHORT → session lives only for transaction duration
2. After flush/clear, entities move to Young Gen → collected quickly
3. Avoid: long transactions with growing entity sets
4. Monitor: session entity count per request (should be < 100 for typical OLTP)
5. Consider readOnly=true: some providers skip snapshot storage
6. Use projections for read-only queries (no entity management overhead)
```

---

## 5. Connection Pool Memory

### Per-Connection Memory Cost

```
┌──────────────────────────────────────────────────────────────┐
│ Memory per database connection                                │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  JDBC Connection object:              ~1-2 KB                 │
│  Socket buffer (send + receive):      ~64-128 KB             │
│  PreparedStatement cache:             ~100 KB - 5 MB         │
│    (depends on statements cached × plan size)                 │
│  Driver internal buffers:             ~50-500 KB             │
│                                                                │
│  TOTAL per connection:                ~200 KB - 5 MB         │
│                                                                │
│  Pool of 20 connections:              ~4 MB - 100 MB         │
│  Pool of 50 connections:              ~10 MB - 250 MB        │
│                                                                │
│  Plus on DATABASE side per connection:                        │
│  PostgreSQL:   ~5-10 MB per backend process                   │
│  MySQL:        ~1-5 MB per thread                            │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### HikariCP Memory Configuration

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20        # Max connections
      minimum-idle: 5              # Min idle connections maintained
      connection-timeout: 30000    # Wait for connection (ms)
      idle-timeout: 600000         # Close idle > 10 min
      max-lifetime: 1800000        # Recycle connections > 30 min
      
      # PreparedStatement caching (if not handled by driver)
      data-source-properties:
        cachePrepStmts: true
        prepStmtCacheSize: 250     # Number of statements cached
        prepStmtCacheSqlLimit: 2048  # Max SQL length to cache
```

### MySQL vs PostgreSQL ResultSet Memory

```java
// MySQL DEFAULT BEHAVIOR: loads ENTIRE ResultSet into memory!
// Query returns 1M rows → 1M rows loaded into Java heap immediately

// Fix for MySQL streaming:
@QueryHints(@QueryHint(name = "org.hibernate.fetchSize", value = "" + Integer.MIN_VALUE))
@Query("SELECT u FROM User u")
Stream<User> streamAllUsers();
// Integer.MIN_VALUE signals MySQL driver to use streaming

// PostgreSQL: uses server-side cursor with fetchSize
@QueryHints(@QueryHint(name = "org.hibernate.fetchSize", value = "100"))
@Query("SELECT u FROM User u")  
Stream<User> streamAllUsers();
// Only 100 rows fetched at a time (true streaming)

// CRITICAL: Must be inside @Transactional for PostgreSQL cursors!
// Autocommit mode closes cursor immediately
```

---

## 6. Collection Initialization Memory Patterns

### Loading Large Collections

```java
// DANGER: Loading a @OneToMany with 10,000 children
@Entity
public class Department {
    @OneToMany(mappedBy = "department")
    private List<Employee> employees;  // 10,000 employees!
}

Department dept = em.find(Department.class, 1L);
dept.getEmployees().size();  // Triggers loading ALL 10,000 employees
// Memory: 10,000 × ~1KB = ~10MB just for this one collection!
// Plus: persistence context overhead for all 10,000 entities
```

### Extra-Lazy Collections

```java
@Entity
public class Department {
    
    @OneToMany(mappedBy = "department")
    @LazyCollection(LazyCollectionOption.EXTRA)
    private List<Employee> employees;
}

// With EXTRA lazy:
dept.getEmployees().size();        // SELECT COUNT(*) FROM employees WHERE dept_id=?
                                    // Does NOT load entities!

dept.getEmployees().contains(emp); // SELECT 1 FROM employees WHERE id=? AND dept_id=?
                                    // Only checks existence!

dept.getEmployees().get(5);        // SELECT * FROM employees WHERE dept_id=? LIMIT 1 OFFSET 5
                                    // Loads single entity!

// MUCH better for large collections where you don't need all elements
```

### Collection Type Memory Characteristics

```
┌───────────────────────────────────────────────────────────────┐
│ Collection Type Comparison                                     │
├─────────────────┬─────────────────┬───────────────────────────┤
│ Type            │ Internal Storage│ Memory Characteristics     │
├─────────────────┼─────────────────┼───────────────────────────┤
│ PersistentBag   │ ArrayList       │ No dedup, allows nulls    │
│ (List, no idx)  │                 │ O(N) contains check       │
│                 │                 │ No extra overhead          │
├─────────────────┼─────────────────┼───────────────────────────┤
│ PersistentList  │ ArrayList       │ Ordered by @OrderColumn   │
│ (List + idx)    │                 │ Index maintenance cost     │
│                 │                 │ Same as ArrayList memory   │
├─────────────────┼─────────────────┼───────────────────────────┤
│ PersistentSet   │ HashSet         │ O(1) contains             │
│ (Set)           │                 │ +16 bytes per entry (hash) │
│                 │                 │ Requires equals/hashCode   │
│                 │                 │ MUST load all to add!      │
├─────────────────┼─────────────────┼───────────────────────────┤
│ PersistentMap   │ HashMap         │ +32 bytes per entry       │
│ (Map)           │                 │ Key + value storage        │
└─────────────────┴─────────────────┴───────────────────────────┘

IMPORTANT: PersistentSet must load ALL elements before adding new one
(to check for duplicates via equals)!
→ Use List (Bag) for large collections where you mainly ADD items
```

---

## 7. Second-Level Cache Memory Management

### Cache Stores Dehydrated State

```
┌──────────────────────────────────────────────────────────────┐
│ L2 Cache Entry Structure (NOT entity instances!)              │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Entity in Persistence Context:                               │
│  ┌──────────────────────────────────────┐                    │
│  │ User(id=1, name="John", email="j@x") │  Full object       │
│  │ + EntityEntry + snapshot              │  ~1.5 KB           │
│  └──────────────────────────────────────┘                    │
│                                                                │
│  Same entity in L2 Cache:                                     │
│  ┌──────────────────────────────────────┐                    │
│  │ CacheEntry {                         │                    │
│  │   disassembledState: Object[] {      │  Dehydrated!       │
│  │     "John",                          │  No object graph   │
│  │     "j@x",                           │  No proxies        │
│  │     30,                              │  Just raw values   │
│  │   },                                 │                    │
│  │   subclass: "User",                  │  ~200-400 bytes    │
│  │   version: 1                         │                    │
│  │ }                                    │                    │
│  └──────────────────────────────────────┘                    │
│                                                                │
│  Key insight:                                                  │
│  - L2 cache stores ~3-5x LESS memory per entity than PC     │
│  - No identity guarantee (each session assembles fresh copy) │
│  - No snapshot needed (cache is read-only copy)              │
│  - Shared across all sessions (amortized cost)               │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### Cache Region Sizing

```yaml
# EhCache configuration
spring:
  cache:
    jcache:
      config: classpath:ehcache.xml
```

```xml
<!-- ehcache.xml -->
<config xmlns="http://www.ehcache.org/v3">
    
    <!-- Frequently accessed, rarely changed entities -->
    <cache alias="com.example.Product">
        <heap unit="entries">10000</heap>  <!-- 10K entities in heap -->
        <expiry>
            <ttl unit="minutes">60</ttl>
        </expiry>
    </cache>
    
    <!-- Large entity, keep fewer in cache -->
    <cache alias="com.example.Order">
        <heap unit="MB">50</heap>  <!-- 50MB max for this region -->
        <expiry>
            <ttl unit="minutes">10</ttl>
        </expiry>
    </cache>
    
    <!-- Off-heap for large datasets (avoids GC) -->
    <cache alias="com.example.CustomerProfile">
        <heap unit="entries">1000</heap>          <!-- Hot data on-heap -->
        <offheap unit="MB">500</offheap>          <!-- 500MB off-heap -->
    </cache>
</config>
```

### Off-Heap Caching (Avoiding GC Pressure)

```
On-Heap Cache:
├── Stored as Java objects in JVM heap
├── Subject to GC (can cause long pauses with large caches)
├── Faster access (direct object references)
└── Limited by JVM heap size

Off-Heap Cache (EhCache BigMemory, Hazelcast HD):
├── Stored in native memory outside JVM heap
├── NOT subject to GC (no GC pauses from cache!)
├── Slightly slower (serialization/deserialization needed)
├── Can be MUCH larger (limited only by system RAM)
└── Ideal for: large reference data caches (100GB+)

Example: 2 million Product entities cached
On-Heap: ~800MB → adds GC pressure, long pauses
Off-Heap: ~800MB in native memory → no GC impact
```

---

## 8. Memory Leak Patterns

### Pattern 1: EntityManager Not Closed

```java
// WRONG: manual EntityManager without closing
public void processData() {
    EntityManager em = emf.createEntityManager();
    em.getTransaction().begin();
    // ... do work ...
    em.getTransaction().commit();
    // FORGOT em.close()!
    // Session + PersistenceContext + all entities remain in memory
    // If called repeatedly: memory leak
}

// RIGHT: always use try-with-resources or Spring management
public void processData() {
    EntityManager em = emf.createEntityManager();
    try {
        em.getTransaction().begin();
        // ... do work ...
        em.getTransaction().commit();
    } catch (Exception e) {
        em.getTransaction().rollback();
        throw e;
    } finally {
        em.close();  // ALWAYS close!
    }
}

// BEST: let Spring manage (auto-closed after @Transactional)
@Transactional
public void processData() {
    // EntityManager auto-created and auto-closed by Spring
}
```

### Pattern 2: ThreadLocal EntityManager Leak

```java
// DANGEROUS in thread pools:
// If EntityManager stored in ThreadLocal and thread is reused...
private static ThreadLocal<EntityManager> emHolder = new ThreadLocal<>();

// Thread pool reuses threads → old EM with stale data persists
// Solution: ALWAYS clear ThreadLocal in finally block
// Or better: use Spring's transaction-scoped EntityManager
```

### Pattern 3: Detached Entity Reference Chains

```java
// Entity loaded in one transaction, referenced in singleton service
@Service
public class CacheService {
    private Map<Long, User> localCache = new ConcurrentHashMap<>();
    
    @Transactional
    public User getUser(Long id) {
        return localCache.computeIfAbsent(id, 
            key -> userRepository.findById(key).get());
        // User is DETACHED after transaction ends
        // But still references lazy collections (PersistentSet/List)
        // PersistentSet holds reference to the Session that loaded it!
        // If Session was pooled/reused → stale reference
        // If Session was closed → LazyInitializationException
    }
}

// Solution: use DTOs in application-level caches, never entities
```

---

## 9. Production Memory Tuning Checklist

### JVM Heap Sizing Formula

```
Required Heap = Base Application
              + (Concurrent Sessions × Avg Entities Per Session × Bytes Per Entity)
              + Connection Pool Memory
              + L2 Cache (on-heap portion)
              + Framework Overhead (Spring, etc.)
              + Headroom (30-50% for GC efficiency)

Example calculation:
─────────────────────
Base application:                    200 MB
Concurrent sessions: 100
Avg entities per session: 50
Bytes per entity: ~1.5 KB
Session memory: 100 × 50 × 1.5 KB = 7.5 MB

Connection pool (20 connections):    40 MB
L2 cache (on-heap):                  100 MB
Framework overhead:                   100 MB
Subtotal:                            447.5 MB
Headroom (50%):                      224 MB
─────────────────────────────────────────────
TOTAL recommended heap:              ~672 MB → set -Xmx768m
```

### Monitoring Alert Thresholds

```yaml
# Prometheus/Grafana alerting rules (pseudo)
alerts:
  - name: SessionEntityCountHigh
    condition: hibernate_session_entity_count > 500
    for: 5m
    severity: warning
    
  - name: SessionEntityCountCritical
    condition: hibernate_session_entity_count > 5000
    for: 1m
    severity: critical
    
  - name: HeapUsageHigh
    condition: jvm_heap_usage_percent > 80
    for: 10m
    severity: warning
    
  - name: GCPauseLong
    condition: jvm_gc_pause_seconds > 2
    severity: warning
    
  - name: ConnectionPoolNearExhaustion
    condition: hikari_connections_active / hikari_connections_max > 0.8
    for: 5m
    severity: warning
```

---

## 10. Memory-Optimized Architecture Patterns

### CQRS Memory Optimization

```
WRITE SIDE:
├── Rich JPA entities (small aggregates)
├── Transactions are short and focused
├── Session contains only the aggregate being modified (~5-20 entities)
├── Heavy memory overhead is acceptable (it's brief)
└── Memory: ~50 KB per write operation

READ SIDE:
├── DTO projections (no entity management)
├── @Transactional(readOnly = true)
├── No persistence context overhead
├── No snapshots stored
└── Memory: ~5 KB per read operation (just the DTO)

interface OrderProjection {
    Long getId();
    String getCustomerName();
    BigDecimal getTotal();
    String getStatus();
}

// This returns lightweight projections, NOT managed entities
// Zero persistence context overhead!
List<OrderProjection> results = orderRepository
    .findAllProjectedBy(pageable);
```

### Aggregate Boundaries for Memory Control

```
LARGE AGGREGATE (memory expensive):
┌─────────────────────────────┐
│ Department                   │
│ ├── List<Employee> (1000)   │  Loading Department loads 1000 employees
│ ├── List<Project> (50)      │  = ~1,050 entities in session
│ └── Budget                   │  = ~1 MB per Department access
└─────────────────────────────┘

BETTER: Smaller aggregates
┌──────────────────┐     ┌──────────────────┐
│ Department       │     │ Employee         │
│ ├── name         │     │ ├── name         │
│ ├── Budget       │     │ ├── departmentId │ (just ID, not relation)
│ └── managerId    │     │ └── skills       │
└──────────────────┘     └──────────────────┘
                         
Loading Department: 1 entity, ~1 KB
Loading Employee list: separate query with pagination
```

### Key Takeaways

1. **Every managed entity costs ~1-2 KB of overhead** beyond its own data (snapshot + metadata)
2. **Strings and collections are stored TWICE** (entity + snapshot)
3. **Session.clear() is your friend** for batch processing
4. **StatelessSession for bulk operations** - zero overhead
5. **MySQL loads entire ResultSet by default** - use streaming mode for large queries
6. **L2 cache is cheaper than PC** - dehydrated state, shared across sessions
7. **Monitor entity count per session** - alert if > 500
8. **Use projections for reads** - no PC overhead at all
9. **Keep aggregates small** - smaller = less memory per transaction
10. **Disable OSIV** - prevents session from growing across entire request lifecycle
