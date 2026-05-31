# Hibernate Architecture & Internals - Interview Questions (Q21-Q40)

---

## Q21: Explain Hibernate architecture and its main components

**Answer:**

Hibernate architecture is layered between the Java application and the database, providing an abstraction over JDBC.

```
┌─────────────────────────────────┐
│        Java Application         │
├─────────────────────────────────┤
│      Hibernate Framework        │
│  ┌───────────────────────────┐  │
│  │   Configuration           │  │
│  │   SessionFactory           │  │
│  │   Session                  │  │
│  │   Transaction              │  │
│  │   Query (HQL/Criteria)     │  │
│  │   First-Level Cache        │  │
│  │   Second-Level Cache       │  │
│  └───────────────────────────┘  │
├─────────────────────────────────┤
│          JDBC / JTA             │
├─────────────────────────────────┤
│          Database               │
└─────────────────────────────────┘
```

**Main Components:**

| Component | Purpose |
|-----------|---------|
| **Configuration** | Reads hibernate.cfg.xml or properties, bootstraps SessionFactory |
| **SessionFactory** | Heavyweight, thread-safe factory for Session objects. One per database. |
| **Session** | Lightweight, single-threaded unit of work. Wraps a JDBC connection. |
| **Transaction** | Abstracts underlying JDBC/JTA transaction |
| **Query** | HQL, Criteria API, or native SQL execution |
| **Persistent Objects** | POJOs mapped to database tables |
| **First-Level Cache** | Session-scoped cache (mandatory) |
| **Second-Level Cache** | SessionFactory-scoped cache (optional) |

**Key Interfaces:**

```java
// Core interfaces
org.hibernate.SessionFactory
org.hibernate.Session
org.hibernate.Transaction
org.hibernate.query.Query
org.hibernate.cfg.Configuration
```

---

## Q22: What is SessionFactory? How is it created?

**Answer:**

`SessionFactory` is a **heavyweight, immutable, thread-safe** object that is created once during application startup. It holds compiled mappings, configuration, and second-level cache data.

**Characteristics:**
- One `SessionFactory` per database (per DataSource)
- Expensive to create (parses mappings, validates schema)
- Thread-safe — shared across all threads
- Immutable after creation
- Holds second-level cache

**Creation (Native Hibernate):**

```java
// Hibernate 5+ using StandardServiceRegistry
StandardServiceRegistry registry = new StandardServiceRegistryBuilder()
    .configure("hibernate.cfg.xml") // loads config
    .build();

SessionFactory sessionFactory = new MetadataSources(registry)
    .buildMetadata()
    .buildSessionFactory();
```

**Creation (Spring Boot — automatic):**

Spring Boot auto-configures the `SessionFactory` (wrapped as `EntityManagerFactory`):

```java
@Autowired
private EntityManagerFactory entityManagerFactory;

// If you need the raw SessionFactory:
SessionFactory sessionFactory = entityManagerFactory.unwrap(SessionFactory.class);
```

**Old deprecated way (Hibernate 4 and below):**

```java
// Deprecated
Configuration cfg = new Configuration().configure();
SessionFactory factory = cfg.buildSessionFactory();
```

**Important:** Never create multiple SessionFactory instances for the same database — it wastes resources and can cause cache inconsistencies.

---

## Q23: What is Session in Hibernate? Is it thread-safe?

**Answer:**

`Session` is a **lightweight, short-lived** object representing a single unit of work with the database. It wraps a JDBC connection and provides the first-level cache.

**Key facts:**
- ❌ **NOT thread-safe** — never share across threads
- Represents a single database conversation
- Holds the first-level (persistence context) cache
- Obtained from `SessionFactory`
- Should be opened and closed per request/transaction

**Responsibilities:**
- CRUD operations (save, update, delete, get, load)
- Query execution
- Transaction management
- First-level caching
- Dirty checking

```java
// Proper usage pattern
Session session = sessionFactory.openSession();
Transaction tx = null;
try {
    tx = session.beginTransaction();
    
    Employee emp = session.get(Employee.class, 1L);
    emp.setName("Updated Name"); // dirty checking will auto-update
    
    tx.commit();
} catch (Exception e) {
    if (tx != null) tx.rollback();
    throw e;
} finally {
    session.close();
}
```

**In Spring Boot**, you typically don't manage Sessions directly — Spring's `@Transactional` handles session lifecycle:

```java
@Service
public class EmployeeService {
    
    @Autowired
    private EmployeeRepository repo;
    
    @Transactional
    public void updateEmployee(Long id, String name) {
        Employee emp = repo.findById(id).orElseThrow();
        emp.setName(name); // auto dirty-checked, auto-flushed at commit
    }
}
```

---

## Q24: What is the difference between Session and EntityManager?

**Answer:**

| Aspect | Session | EntityManager |
|--------|---------|---------------|
| **Specification** | Hibernate-specific | JPA standard |
| **Package** | `org.hibernate.Session` | `javax.persistence.EntityManager` |
| **Portability** | Tied to Hibernate | Works with any JPA provider |
| **Features** | More features (e.g., `evict()`, `isDirty()`) | Standard subset |
| **Underlying** | — | Wraps Session in Hibernate |

`EntityManager` is the JPA standard interface. When using Hibernate as the JPA provider, `EntityManager` delegates to `Session` internally.

```java
// Getting Session from EntityManager
@PersistenceContext
private EntityManager entityManager;

public void doSomething() {
    Session session = entityManager.unwrap(Session.class);
    // Now you can use Hibernate-specific features
    session.enableFilter("activeOnly");
}
```

**Method mapping:**

| JPA (EntityManager) | Hibernate (Session) |
|---------------------|---------------------|
| `persist()` | `save()` / `persist()` |
| `merge()` | `merge()` / `update()` |
| `remove()` | `delete()` |
| `find()` | `get()` |
| `getReference()` | `load()` |
| `createQuery()` | `createQuery()` |
| `flush()` | `flush()` |
| `detach()` | `evict()` |

**Best Practice:** Use `EntityManager` (JPA) for portability. Use `Session` only when you need Hibernate-specific features like filters, `ScrollableResults`, or `StatelessSession`.

---

## Q25: What is Hibernate Configuration? hibernate.cfg.xml vs application.properties

**Answer:**

Hibernate configuration defines database connection details, dialect, mappings, and behavioral settings.

**hibernate.cfg.xml (Standalone Hibernate):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE hibernate-configuration PUBLIC
    "-//Hibernate/Hibernate Configuration DTD 3.0//EN"
    "http://www.hibernate.org/dtd/hibernate-configuration-3.0.dtd">

<hibernate-configuration>
    <session-factory>
        <!-- Database connection -->
        <property name="hibernate.connection.driver_class">com.mysql.cj.jdbc.Driver</property>
        <property name="hibernate.connection.url">jdbc:mysql://localhost:3306/mydb</property>
        <property name="hibernate.connection.username">root</property>
        <property name="hibernate.connection.password">secret</property>
        
        <!-- Hibernate settings -->
        <property name="hibernate.dialect">org.hibernate.dialect.MySQL8Dialect</property>
        <property name="hibernate.show_sql">true</property>
        <property name="hibernate.format_sql">true</property>
        <property name="hibernate.hbm2ddl.auto">update</property>
        
        <!-- Connection pool -->
        <property name="hibernate.c3p0.min_size">5</property>
        <property name="hibernate.c3p0.max_size">20</property>
        
        <!-- Mappings -->
        <mapping class="com.example.Employee"/>
    </session-factory>
</hibernate-configuration>
```

**application.properties (Spring Boot):**

```properties
# DataSource
spring.datasource.url=jdbc:mysql://localhost:3306/mydb
spring.datasource.username=root
spring.datasource.password=secret
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver

# JPA/Hibernate
spring.jpa.database-platform=org.hibernate.dialect.MySQL8Dialect
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true
spring.jpa.hibernate.ddl-auto=update

# HikariCP (default in Spring Boot 2+)
spring.datasource.hikari.minimum-idle=5
spring.datasource.hikari.maximum-pool-size=20
spring.datasource.hikari.idle-timeout=30000
```

**Key Differences:**

| Aspect | hibernate.cfg.xml | application.properties |
|--------|-------------------|------------------------|
| Used by | Standalone Hibernate | Spring Boot |
| Format | XML | Key-value properties (or YAML) |
| Mapping declaration | Explicit `<mapping>` tags | Auto-scan via `@Entity` |
| Connection pool | Manual (C3P0/DBCP) | HikariCP auto-configured |
| Multiple databases | Multiple cfg files | Multiple `@Configuration` classes |

---

## Q26: What is Dialect in Hibernate? Why is it needed?

**Answer:**

A `Dialect` tells Hibernate how to generate SQL specific to a particular database. Each database has its own SQL variations (pagination, data types, functions, identity generation).

**Why needed:**
- Different databases use different SQL syntax
- Pagination: MySQL uses `LIMIT`, Oracle uses `ROWNUM`/`FETCH FIRST`
- Auto-increment: MySQL `AUTO_INCREMENT`, PostgreSQL `SERIAL`, Oracle `SEQUENCE`
- Data types: `VARCHAR` vs `VARCHAR2`, `BOOLEAN` support varies
- Functions: `NOW()` vs `SYSDATE` vs `CURRENT_TIMESTAMP`

**Common Dialects:**

```java
// MySQL
org.hibernate.dialect.MySQL8Dialect
org.hibernate.dialect.MySQLDialect

// PostgreSQL
org.hibernate.dialect.PostgreSQLDialect
org.hibernate.dialect.PostgreSQL10Dialect

// Oracle
org.hibernate.dialect.Oracle12cDialect

// SQL Server
org.hibernate.dialect.SQLServer2016Dialect

// H2 (testing)
org.hibernate.dialect.H2Dialect
```

**Configuration:**

```properties
# Spring Boot
spring.jpa.database-platform=org.hibernate.dialect.PostgreSQLDialect

# Or let Hibernate auto-detect (Hibernate 6+):
# spring.jpa.database-platform is optional if driver is on classpath
```

**Custom Dialect (rare):**

```java
public class CustomMySQL8Dialect extends MySQL8Dialect {
    
    public CustomMySQL8Dialect() {
        super();
        // Register custom function
        registerFunction("group_concat",
            new StandardSQLFunction("group_concat", StandardBasicTypes.STRING));
    }
    
    @Override
    public String getTableTypeString() {
        return " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";
    }
}
```

**Hibernate 6+ Note:** Dialect resolution is now automatic in most cases based on the JDBC driver/connection metadata. Explicit dialect configuration is becoming optional.

---

## Q27: What is the difference between getCurrentSession() and openSession()?

**Answer:**

| Aspect | `getCurrentSession()` | `openSession()` |
|--------|----------------------|-----------------|
| **Session management** | Bound to current context (thread/transaction) | Creates a brand new session |
| **Closing** | Auto-closed when transaction commits/rollbacks | Must be explicitly closed |
| **Thread binding** | Returns same session for same thread/transaction | Always creates new instance |
| **Configuration** | Requires `current_session_context_class` | Works without extra config |
| **Use case** | Managed environments (Spring, JTA) | Manual session management |

```java
// openSession() — you manage the lifecycle
Session session = sessionFactory.openSession();
try {
    Transaction tx = session.beginTransaction();
    session.save(entity);
    tx.commit();
} finally {
    session.close(); // YOU must close it
}

// getCurrentSession() — context-managed
// Requires: hibernate.current_session_context_class=thread
Session session = sessionFactory.getCurrentSession();
session.beginTransaction();
session.save(entity);
session.getTransaction().commit();
// session is auto-closed after commit
```

**Configuration for `getCurrentSession()`:**

```properties
hibernate.current_session_context_class=thread
# Options: thread, jta, managed, spring
```

**In Spring Boot:** You almost never call either directly. Spring's `@Transactional` uses `getCurrentSession()` internally, binding the session to the current transaction:

```java
@Transactional
public void saveEmployee(Employee emp) {
    // Spring opens session, binds to transaction
    entityManager.persist(emp);
    // Spring commits transaction, closes session
}
```

---

## Q28: Explain Hibernate object states/lifecycle

**Answer:**

Every entity in Hibernate exists in one of four states:

```
┌──────────┐   save()/persist()   ┌────────────┐
│ Transient │ ──────────────────► │ Persistent │
└──────────┘                      └────────────┘
     ▲                                  │  ▲
     │                     evict()/     │  │  merge()/
     │                     close()/     │  │  update()/
     │  new Object()       clear()      ▼  │  saveOrUpdate()
     │                            ┌──────────┐
     │                            │ Detached  │
     │                            └──────────┘
     │                                  │
     │         delete()                 │ delete()
     ▼◄─────────────────────────────────┘
┌──────────┐
│ Removed  │
└──────────┘
```

**1. Transient:**
- Newly created with `new`, not associated with any Session
- No database representation
- Not tracked by Hibernate
- Garbage collected when no references exist

```java
Employee emp = new Employee(); // Transient
emp.setName("John");
// No ID assigned, no session involvement
```

**2. Persistent (Managed):**
- Associated with an open Session
- Has a database identity (primary key)
- Changes are **automatically detected** (dirty checking) and synced to DB
- Exists in the first-level cache

```java
Session session = sessionFactory.openSession();
session.beginTransaction();

Employee emp = new Employee();
emp.setName("John");
session.save(emp); // Now PERSISTENT — emp has an ID

emp.setName("Jane"); // Dirty checking detects this change
// UPDATE will be issued at flush/commit automatically

session.getTransaction().commit();
```

**3. Detached:**
- Was persistent but the Session was closed/cleared
- Still has a database identity
- Changes are NOT tracked
- Can be reattached using `merge()` or `update()`

```java
session.close(); 
// emp is now DETACHED

emp.setName("Updated"); // NOT tracked by any session

// Reattach in new session:
Session newSession = sessionFactory.openSession();
newSession.beginTransaction();
newSession.merge(emp); // or update(emp) — makes it persistent again
newSession.getTransaction().commit();
```

**4. Removed:**
- Scheduled for deletion
- Still associated with Session until flush
- Will be deleted from DB at flush/commit

```java
session.delete(emp); // REMOVED state
// DELETE SQL issued at flush/commit
```

---

## Q29: What is Dirty Checking in Hibernate? How does it work?

**Answer:**

Dirty checking is Hibernate's mechanism to **automatically detect changes** to persistent entities and generate appropriate UPDATE SQL at flush time — without requiring explicit `update()` calls.

**How it works internally:**

1. When an entity becomes persistent (loaded or saved), Hibernate takes a **snapshot** of all property values
2. At flush time, Hibernate compares current property values against the snapshot
3. If any difference is found, the entity is "dirty" and an UPDATE is generated
4. Only changed columns are updated (with `@DynamicUpdate`)

```java
@Transactional
public void updateSalary(Long empId, double newSalary) {
    Employee emp = entityManager.find(Employee.class, empId);
    // Hibernate takes snapshot: {name="John", salary=50000}
    
    emp.setSalary(newSalary);
    // No explicit save/update needed!
    
    // At flush (before commit):
    // Hibernate compares current state vs snapshot
    // Detects salary changed → generates UPDATE
}
// Generated: UPDATE employee SET salary=? WHERE id=?
```

**Performance implications:**

- Snapshot comparison happens for ALL managed entities at flush
- For read-heavy operations with many entities, this can be expensive
- Mitigation strategies:

```java
// 1. Read-only transactions (no dirty checking)
@Transactional(readOnly = true)
public List<Employee> getAllEmployees() {
    return repo.findAll();
}

// 2. StatelessSession (no caching, no dirty checking)
StatelessSession stateless = sessionFactory.openStatelessSession();
Employee emp = (Employee) stateless.get(Employee.class, 1L);
emp.setName("New");
stateless.update(emp); // Explicit update required

// 3. Clear session to release snapshots
entityManager.clear();

// 4. Use projections/DTOs for read-only queries
@Query("SELECT new com.example.EmpDTO(e.name, e.salary) FROM Employee e")
List<EmpDTO> findAllDTOs();
```

---

## Q30: What is Automatic Dirty Checking?

**Answer:**

Automatic Dirty Checking means Hibernate **automatically** updates the database when a persistent entity's state changes within a transaction — no explicit `save()` or `update()` call needed.

```java
@Service
public class AccountService {
    
    @Autowired
    private EntityManager em;
    
    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        Account from = em.find(Account.class, fromId);
        Account to = em.find(Account.class, toId);
        
        from.debit(amount);   // Changes detected automatically
        to.credit(amount);    // Changes detected automatically
        
        // NO em.merge() or em.persist() needed!
        // At transaction commit → flush → dirty check → 2 UPDATE statements
    }
}
```

**When does flushing (and dirty checking) happen?**

1. Before transaction commit
2. Before a query executes (to ensure query sees latest state)
3. When `flush()` is called explicitly

**Controlling flush behavior:**

```java
// Change flush mode
entityManager.setFlushMode(FlushModeType.COMMIT); // Only flush at commit
entityManager.setFlushMode(FlushModeType.AUTO);   // Default — flush before queries too

// Hibernate-specific modes
session.setHibernateFlushMode(FlushMode.MANUAL);  // Never auto-flush
```

**@DynamicUpdate — only update changed columns:**

```java
@Entity
@DynamicUpdate // Only include modified columns in UPDATE
public class Employee {
    @Id
    private Long id;
    private String name;
    private String email;
    private double salary;
}

// If only salary changes:
// Without @DynamicUpdate: UPDATE employee SET name=?, email=?, salary=? WHERE id=?
// With @DynamicUpdate:    UPDATE employee SET salary=? WHERE id=?
```

---

## Q31: What is the purpose of flush() and clear() in Hibernate?

**Answer:**

**`flush()`** — Synchronizes the persistence context (in-memory state) with the database. Executes pending SQL statements but does NOT commit the transaction.

**`clear()`** — Evicts all entities from the first-level cache (persistence context). Entities become detached.

```java
// flush() - push changes to DB (within transaction)
entityManager.flush();
// SQL is executed but transaction is still active
// Can still rollback!

// clear() - detach all managed entities
entityManager.clear();
// All entities are now detached
// First-level cache is empty
// Further changes to those objects won't be tracked
```

**Common use case — Batch processing:**

```java
@Transactional
public void batchInsert(List<EmployeeDTO> employees) {
    int batchSize = 50;
    
    for (int i = 0; i < employees.size(); i++) {
        Employee emp = new Employee(employees.get(i));
        entityManager.persist(emp);
        
        if (i % batchSize == 0 && i > 0) {
            entityManager.flush();  // Execute INSERT statements
            entityManager.clear();  // Release memory (detach entities)
        }
    }
}
```

Without `flush()` + `clear()`, persisting 100K entities would keep all 100K objects in the first-level cache → `OutOfMemoryError`.

**`evict()` / `detach()`** — Remove a single entity from the persistence context:

```java
entityManager.detach(singleEntity); // JPA
session.evict(singleEntity);        // Hibernate
```

**Flush modes summary:**

| Mode | Behavior |
|------|----------|
| `AUTO` (default) | Flush before queries and at commit |
| `COMMIT` | Flush only at commit |
| `MANUAL` | Never auto-flush; you must call `flush()` explicitly |

---

## Q32: What is the difference between save(), persist(), saveOrUpdate(), merge(), update()?

**Answer:**

| Method | Return | ID Generation | State Transition | Detached Entity |
|--------|--------|---------------|------------------|-----------------|
| `save()` | Serializable (ID) | Immediate | Transient → Persistent | Works (creates new) |
| `persist()` | void | May delay | Transient → Persistent | Throws exception |
| `update()` | void | — | Detached → Persistent | Reattaches |
| `saveOrUpdate()` | void | Depends | Transient/Detached → Persistent | Reattaches |
| `merge()` | Entity (copy) | — | Returns managed copy | Returns merged copy |

**Detailed behavior:**

```java
// save() — Hibernate-specific, returns generated ID immediately
Serializable id = session.save(transientEntity);
// INSERT may execute immediately (depends on ID generator)

// persist() — JPA standard, void return
session.persist(transientEntity);
// INSERT can be delayed until flush (if ID generator allows)
// Throws PersistenceException if entity is detached

// update() — Reattach a detached entity
session.update(detachedEntity);
// Throws exception if another instance with same ID is already in session
// Always schedules UPDATE (even if no changes)

// saveOrUpdate() — Hibernate decides based on ID
session.saveOrUpdate(entity);
// If unsaved (ID is null/unsaved-value) → INSERT
// If already has ID → UPDATE (reattach)

// merge() — JPA standard, returns NEW managed instance
Employee managed = (Employee) session.merge(detachedEntity);
// Original detached object is NOT affected
// Returns a managed COPY
// Safe even if another instance with same ID exists in session
```

**Critical difference — merge() vs update():**

```java
Employee emp1 = session.get(Employee.class, 1L); // persistent

Session newSession = sessionFactory.openSession();
Employee emp2 = /* detached copy with id=1 */;

// update() would FAIL — emp1 with same ID already in session
// newSession.update(emp2); // NonUniqueObjectException

// merge() works — returns managed copy, doesn't attach emp2
Employee managed = (Employee) newSession.merge(emp2); // OK
// managed != emp2; managed is the persistent copy
```

**Best practice in Spring Boot:** Use `repository.save()` which internally calls `merge()` for detached entities and `persist()` for new entities (determined by `@Id` value or `Persistable` interface).

---

## Q33: What is the difference between get() and load() in Hibernate?

**Answer:**

| Aspect | `get()` | `load()` |
|--------|---------|----------|
| **DB hit** | Immediately hits DB | Returns a proxy (no DB hit) |
| **Not found** | Returns `null` | Throws `ObjectNotFoundException` (on access) |
| **Return type** | Actual entity object | Proxy (uninitialized) |
| **Use when** | Not sure if entity exists | Sure entity exists |
| **JPA equivalent** | `find()` | `getReference()` |

```java
// get() — immediate SELECT
Employee emp = session.get(Employee.class, 1L);
// SELECT * FROM employee WHERE id = 1  (executes NOW)
if (emp == null) {
    // Entity doesn't exist
}

// load() — returns proxy, no SELECT yet
Employee emp = session.load(Employee.class, 1L);
// No SQL executed yet! emp is a PROXY

emp.getName(); // NOW the SELECT executes (lazy initialization)
// If id=1 doesn't exist → ObjectNotFoundException
```

**Why use `load()`?**

Setting foreign key relationships without loading the related entity:

```java
// Efficient: no SELECT for Department
Department dept = session.load(Department.class, 5L); // proxy only
Employee emp = new Employee();
emp.setDepartment(dept); // Just sets FK = 5
session.save(emp);
// INSERT INTO employee (name, department_id) VALUES (?, 5)
// Never needed to load the Department!
```

**JPA equivalents:**

```java
// find() = get()
Employee emp = entityManager.find(Employee.class, 1L);

// getReference() = load()
Employee empRef = entityManager.getReference(Employee.class, 1L);
```

**LazyInitializationException risk with load():**

```java
Employee emp = session.load(Employee.class, 1L);
session.close();
emp.getName(); // LazyInitializationException! Proxy can't initialize without session
```

---

## Q34: What is Hibernate Proxy? How does lazy loading use proxies?

**Answer:**

A Hibernate Proxy is a **runtime-generated subclass** (using Byte Buddy or CGLIB) that stands in for an entity. It contains only the ID and loads the actual data on first property access.

**How it works:**

```
┌───────────────────────┐
│    Employee$Proxy      │  ← Generated subclass
├───────────────────────┤
│ - id = 1              │  ← Only ID is populated
│ - initialized = false │
│ - session = ...       │  ← Reference to owning session
├───────────────────────┤
│ + getId()             │  ← Returns ID without loading
│ + getName()           │  ← Triggers SELECT on first call
│ + getSalary()         │  ← Triggers SELECT on first call
└───────────────────────┘
```

**Proxy in lazy associations:**

```java
@Entity
public class Employee {
    @Id
    private Long id;
    
    @ManyToOne(fetch = FetchType.LAZY) // Default for @ManyToOne is EAGER!
    private Department department;
}

// When loading Employee:
Employee emp = session.get(Employee.class, 1L);
// SELECT * FROM employee WHERE id=1

emp.getDepartment(); // Returns a Department PROXY (not loaded yet)
emp.getDepartment().getName(); // NOW triggers: SELECT * FROM department WHERE id=?
```

**Checking proxy state:**

```java
// Is it initialized?
boolean loaded = Hibernate.isInitialized(emp.getDepartment());

// Force initialization
Hibernate.initialize(emp.getDepartment());

// Get real class (not proxy class)
Class<?> realClass = Hibernate.getClass(emp.getDepartment());

// Unproxy (Hibernate 5.2.10+)
Department real = Hibernate.unproxy(emp.getDepartment(), Department.class);
```

**Proxy limitations:**
- Cannot proxy `final` classes or `final` methods
- `instanceof` checks may fail (use `Hibernate.getClass()`)
- Proxy identity: `emp.getDepartment().getClass() != Department.class`
- Requires an open Session — accessing after session close → `LazyInitializationException`

**Collections use a different mechanism:**

```java
@OneToMany(mappedBy = "department", fetch = FetchType.LAZY)
private List<Employee> employees; 
// Not a proxy — uses PersistentBag/PersistentSet/PersistentList
// These are Hibernate wrapper collections that load on first access
```

---

## Q35: What is the difference between Hibernate and JPA?

**Answer:**

| Aspect | JPA | Hibernate |
|--------|-----|-----------|
| **Nature** | Specification (interfaces + annotations) | Implementation (actual code) |
| **Package** | `javax.persistence` / `jakarta.persistence` | `org.hibernate` |
| **Defined by** | Jakarta EE (formerly Java EE) | Red Hat / Community |
| **Standalone** | No — needs a provider | Yes — works alone |
| **Other providers** | EclipseLink, OpenJPA, DataNucleus | — |

**JPA is the spec, Hibernate is the most popular implementation:**

```java
// JPA interfaces (portable)
@Entity                              // javax.persistence
EntityManager em;                    // javax.persistence
em.persist(entity);
em.find(Entity.class, id);
em.createQuery("SELECT e FROM Employee e", Employee.class);

// Hibernate-specific (non-portable but more features)
Session session;                     // org.hibernate
session.save(entity);
session.get(Entity.class, id);
session.createQuery("FROM Employee"); // HQL
session.enableFilter("tenantFilter");
session.setHibernateFlushMode(FlushMode.MANUAL);
```

**Hibernate extras not in JPA:**
- `@Formula` — computed SQL columns
- `@Where`, `@Filter` — entity-level SQL filters
- `@BatchSize` — batch lazy loading
- `@DynamicUpdate`, `@DynamicInsert`
- `@NaturalId` — business key lookup with caching
- `StatelessSession` — no cache, no dirty checking
- Multi-tenancy support
- Custom ID generators
- `ScrollableResults` for cursor-based iteration
- Soft delete (`@SoftDelete` in Hibernate 6.4+)

**Best practice:** Code to JPA interfaces for portability; use Hibernate-specific features only when needed.

---

## Q36: Explain the Hibernate Interceptor and Event system

**Answer:**

Hibernate provides two mechanisms for hooking into entity lifecycle: **Interceptors** (older) and **Event Listeners** (newer, preferred).

### Interceptors

```java
public class AuditInterceptor extends EmptyInterceptor {

    @Override
    public boolean onSave(Object entity, Serializable id,
                          Object[] state, String[] propertyNames, Type[] types) {
        if (entity instanceof Auditable) {
            for (int i = 0; i < propertyNames.length; i++) {
                if ("createdDate".equals(propertyNames[i])) {
                    state[i] = LocalDateTime.now();
                    return true; // state was modified
                }
            }
        }
        return false;
    }

    @Override
    public boolean onFlushDirty(Object entity, Serializable id,
                                Object[] currentState, Object[] previousState,
                                String[] propertyNames, Type[] types) {
        // Called on update
        if (entity instanceof Auditable) {
            for (int i = 0; i < propertyNames.length; i++) {
                if ("modifiedDate".equals(propertyNames[i])) {
                    currentState[i] = LocalDateTime.now();
                    return true;
                }
            }
        }
        return false;
    }
}
```

**Registering interceptor:**

```java
// Session-scoped
Session session = sessionFactory.withOptions()
    .interceptor(new AuditInterceptor())
    .openSession();

// SessionFactory-scoped (Spring Boot)
@Configuration
public class HibernateConfig {
    @Bean
    public HibernatePropertiesCustomizer hibernateCustomizer() {
        return props -> props.put("hibernate.session_factory.interceptor", 
                                  new AuditInterceptor());
    }
}
```

### Event Listeners (Preferred)

```java
@Component
public class AuditEventListener implements 
        PreInsertEventListener, PreUpdateEventListener {

    @Override
    public boolean onPreInsert(PreInsertEvent event) {
        if (event.getEntity() instanceof Auditable) {
            Auditable entity = (Auditable) event.getEntity();
            entity.setCreatedDate(LocalDateTime.now());
            // Also update the state array for Hibernate
            setPropertyState(event.getState(), event.getPersister(), 
                           "createdDate", LocalDateTime.now());
        }
        return false; // false = don't veto the insert
    }

    @Override
    public boolean onPreUpdate(PreUpdateEvent event) {
        if (event.getEntity() instanceof Auditable) {
            Auditable entity = (Auditable) event.getEntity();
            entity.setModifiedDate(LocalDateTime.now());
            setPropertyState(event.getState(), event.getPersister(), 
                           "modifiedDate", LocalDateTime.now());
        }
        return false;
    }
}
```

### JPA Lifecycle Callbacks (Simplest approach)

```java
@Entity
@EntityListeners(AuditingEntityListener.class) // Spring Data JPA
public class Employee {
    
    @CreatedDate
    private LocalDateTime createdDate;
    
    @LastModifiedDate
    private LocalDateTime modifiedDate;
    
    // Or manual callbacks:
    @PrePersist
    public void prePersist() {
        this.createdDate = LocalDateTime.now();
    }
    
    @PreUpdate
    public void preUpdate() {
        this.modifiedDate = LocalDateTime.now();
    }
}
```

**JPA callback annotations:** `@PrePersist`, `@PostPersist`, `@PreUpdate`, `@PostUpdate`, `@PreRemove`, `@PostRemove`, `@PostLoad`

---

## Q37: What is hibernate.hbm2ddl.auto and its possible values?

**Answer:**

`hibernate.hbm2ddl.auto` (or `spring.jpa.hibernate.ddl-auto` in Spring Boot) controls automatic schema generation/migration based on entity mappings.

| Value | Behavior | Use Case |
|-------|----------|----------|
| `none` | Does nothing | Production |
| `validate` | Validates schema matches entities; throws exception if mismatch | Production / Staging |
| `update` | Updates schema (adds columns/tables, never removes) | Development |
| `create` | Drops and recreates schema on startup | Testing |
| `create-drop` | Creates on startup, drops on SessionFactory close | Unit tests |

```properties
# Spring Boot
spring.jpa.hibernate.ddl-auto=validate

# Native Hibernate
hibernate.hbm2ddl.auto=update
```

**Detailed behavior:**

```
validate:
  - Compares entity mappings to existing schema
  - Throws SchemaManagementException if mismatch
  - Does NOT modify database
  - ✅ Safe for production

update:
  - ADDs new tables, columns, constraints
  - NEVER drops tables/columns (even if entity field removed)
  - May alter column types
  - ⚠️ NOT safe for production (can be unpredictable)

create:
  - DROP all mapped tables
  - CREATE fresh tables from entity mappings
  - ❌ Destroys data

create-drop:
  - Same as create, plus DROP ALL on shutdown
  - ❌ Only for tests
```

**Production best practice:**

```properties
# Production: validate only, use Flyway/Liquibase for migrations
spring.jpa.hibernate.ddl-auto=validate
spring.flyway.enabled=true
```

```java
// Flyway migration example: V1__create_employee.sql
CREATE TABLE employee (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    salary DECIMAL(10,2),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Q38: What is the naming strategy in Hibernate? (Physical vs Implicit)

**Answer:**

Hibernate uses two naming strategies to map Java names to database names:

1. **ImplicitNamingStrategy** — Determines the logical name when no explicit name is provided via `@Table` or `@Column`
2. **PhysicalNamingStrategy** — Transforms ALL logical names (explicit or implicit) into physical database names

```
Java: employeeFirstName
        │
        ▼
ImplicitNamingStrategy (if no @Column specified)
        │ → "employeeFirstName" (logical name)
        ▼
PhysicalNamingStrategy
        │ → "employee_first_name" (physical/DB name)
        ▼
Database column: employee_first_name
```

**Spring Boot default (SpringPhysicalNamingStrategy):**
- Converts camelCase → snake_case
- Converts dots → underscores
- Lowercases everything

```java
@Entity
public class EmployeeDetail {  // Table: employee_detail
    
    private String firstName;   // Column: first_name
    private String lastName;    // Column: last_name
    
    @Column(name = "emp_email") // Explicit: emp_email (physical strategy still applies)
    private String email;
}
```

**Custom PhysicalNamingStrategy:**

```java
public class UpperCaseNamingStrategy implements PhysicalNamingStrategy {

    @Override
    public Identifier toPhysicalTableName(Identifier name, JdbcEnvironment env) {
        return Identifier.toIdentifier(name.getText().toUpperCase());
    }

    @Override
    public Identifier toPhysicalColumnName(Identifier name, JdbcEnvironment env) {
        return Identifier.toIdentifier(
            name.getText().replaceAll("([a-z])([A-Z])", "$1_$2").toUpperCase()
        );
    }

    @Override
    public Identifier toPhysicalCatalogName(Identifier name, JdbcEnvironment env) {
        return name;
    }

    @Override
    public Identifier toPhysicalSchemaName(Identifier name, JdbcEnvironment env) {
        return name;
    }

    @Override
    public Identifier toPhysicalSequenceName(Identifier name, JdbcEnvironment env) {
        return name;
    }
}
```

**Configuration:**

```properties
# Spring Boot
spring.jpa.hibernate.naming.physical-strategy=com.example.UpperCaseNamingStrategy
spring.jpa.hibernate.naming.implicit-strategy=org.hibernate.boot.model.naming.ImplicitNamingStrategyJpaCompliantImpl
```

**Available built-in strategies:**

```
ImplicitNamingStrategy:
- ImplicitNamingStrategyJpaCompliantImpl (JPA default)
- ImplicitNamingStrategyLegacyJpaImpl

PhysicalNamingStrategy:
- CamelCaseToUnderscoresNamingStrategy (Spring Boot default, Hibernate 6)
- PhysicalNamingStrategyStandardImpl (no transformation)
```

---

## Q39: What is the difference between First-Level and Second-Level cache in architecture?

**Answer:**

| Aspect | First-Level Cache | Second-Level Cache |
|--------|-------------------|---------------------|
| **Scope** | Session (EntityManager) | SessionFactory (application-wide) |
| **Lifetime** | Per transaction/session | Application lifetime |
| **Enabled by** | Always (cannot disable) | Explicitly configured |
| **Shared** | No — per thread/session | Yes — across all sessions |
| **Eviction** | `clear()`, `evict()`, session close | Manual, TTL, or capacity-based |
| **Implementation** | Internal HashMap | Ehcache, Hazelcast, Infinispan, Caffeine |
| **Thread safety** | Not needed (session is single-threaded) | Must be thread-safe |

**First-Level Cache (Persistence Context):**

```java
@Transactional
public void demo() {
    // First call — hits DB
    Employee emp1 = entityManager.find(Employee.class, 1L); // SELECT executed
    
    // Second call — same session, returns cached instance
    Employee emp2 = entityManager.find(Employee.class, 1L); // NO SQL
    
    assert emp1 == emp2; // Same object reference! (identity guarantee)
}
```

**Second-Level Cache:**

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Department {
    @Id
    private Long id;
    private String name;
}
```

```properties
# Enable second-level cache
spring.jpa.properties.hibernate.cache.use_second_level_cache=true
spring.jpa.properties.hibernate.cache.region.factory_class=org.hibernate.cache.jcache.JCacheRegionFactory
spring.jpa.properties.javax.cache.provider=org.ehcache.jsr107.EhcacheCachingProvider
```

**Cache lookup order:**

```
find(Employee.class, 1L)
    │
    ▼
1st Level Cache (Session) → HIT? Return entity
    │ MISS
    ▼
2nd Level Cache (SessionFactory) → HIT? Put in 1st level, return
    │ MISS
    ▼
Database → Put in 1st level + 2nd level, return
```

**CacheConcurrencyStrategy options:**

| Strategy | Use case |
|----------|----------|
| `READ_ONLY` | Immutable/reference data |
| `NONSTRICT_READ_WRITE` | Rarely updated, eventual consistency OK |
| `READ_WRITE` | Frequently read, sometimes updated |
| `TRANSACTIONAL` | JTA environments, full ACID on cache |

**Query Cache (separate from entity cache):**

```properties
spring.jpa.properties.hibernate.cache.use_query_cache=true
```

```java
List<Department> depts = entityManager.createQuery(
        "SELECT d FROM Department d", Department.class)
    .setHint("org.hibernate.cacheable", true)
    .getResultList();
// Caches the query result (list of IDs)
// Entity data still comes from 2nd level entity cache
```

---

## Q40: Explain Hibernate's connection pooling (HikariCP, C3P0)

**Answer:**

Connection pooling maintains a pool of reusable database connections, avoiding the overhead of creating/closing connections for every request.

**Spring Boot 2+ uses HikariCP by default** (fastest pool available).

### HikariCP Configuration (Spring Boot default)

```properties
# DataSource
spring.datasource.url=jdbc:mysql://localhost:3306/mydb
spring.datasource.username=root
spring.datasource.password=secret

# HikariCP settings
spring.datasource.hikari.minimum-idle=5
spring.datasource.hikari.maximum-pool-size=20
spring.datasource.hikari.idle-timeout=300000        # 5 min
spring.datasource.hikari.max-lifetime=1800000       # 30 min
spring.datasource.hikari.connection-timeout=30000   # 30 sec
spring.datasource.hikari.pool-name=MyAppPool
spring.datasource.hikari.auto-commit=false
spring.datasource.hikari.leak-detection-threshold=60000  # Log if connection held > 60s
```

### C3P0 Configuration (legacy/standalone Hibernate)

```xml
<!-- In hibernate.cfg.xml -->
<property name="hibernate.c3p0.min_size">5</property>
<property name="hibernate.c3p0.max_size">20</property>
<property name="hibernate.c3p0.acquire_increment">5</property>
<property name="hibernate.c3p0.timeout">1800</property>
<property name="hibernate.c3p0.max_statements">50</property>
```

### Comparison

| Aspect | HikariCP | C3P0 |
|--------|----------|------|
| **Performance** | Fastest (bytecode-level optimizations) | Slower |
| **Codebase** | ~130KB, minimal | Larger, complex |
| **Spring Boot** | Default since 2.0 | Requires explicit config |
| **Connection validation** | Lightweight (isValid()) | Heavyweight (test queries) |
| **Maintenance** | Actively maintained | Largely dormant |

### Pool sizing formula

```
Pool Size = Tn × (Cm − 1) + 1

Where:
- Tn = max number of threads that can execute concurrently
- Cm = max number of simultaneous connections needed per thread

Simplified rule of thumb:
- Pool size ≈ (2 × CPU cores) + number_of_disk_spindles
- For most apps: 10-20 connections suffices for surprising load
```

### Programmatic configuration (Spring Boot)

```java
@Configuration
public class DataSourceConfig {

    @Bean
    @ConfigurationProperties("spring.datasource.hikari")
    public HikariDataSource dataSource() {
        return DataSourceBuilder.create()
            .type(HikariDataSource.class)
            .build();
    }
}
```

### Monitoring pool metrics

```java
@Autowired
private DataSource dataSource;

public void logPoolStats() {
    HikariDataSource hikari = (HikariDataSource) dataSource;
    HikariPoolMXBean pool = hikari.getHikariPoolMXBean();
    
    log.info("Active: {}, Idle: {}, Waiting: {}, Total: {}",
        pool.getActiveConnections(),
        pool.getIdleConnections(),
        pool.getThreadsAwaitingConnection(),
        pool.getTotalConnections());
}
```

**Common issues:**
- **Connection leak:** Enable `leak-detection-threshold`
- **Pool exhaustion:** Increase `maximum-pool-size` or fix slow queries
- **Stale connections:** Set `max-lifetime` less than DB's `wait_timeout`

---

## Summary Table

| Topic | Key Takeaway |
|-------|-------------|
| Architecture | Layered: App → Hibernate → JDBC → DB |
| SessionFactory | One per DB, thread-safe, expensive to create |
| Session | Per-request, NOT thread-safe, first-level cache |
| Object States | Transient → Persistent → Detached → Removed |
| Dirty Checking | Automatic UPDATE detection via snapshot comparison |
| flush/clear | flush = sync to DB; clear = empty cache |
| save vs persist vs merge | persist (JPA), merge (detached), save (returns ID) |
| get vs load | get = immediate; load = proxy (lazy) |
| Proxy | Runtime subclass for lazy loading |
| JPA vs Hibernate | JPA = spec; Hibernate = implementation |
| hbm2ddl.auto | validate in prod; use Flyway/Liquibase for migrations |
| Naming Strategy | Implicit (no annotation) + Physical (final transform) |
| L1 vs L2 Cache | L1 = session-scoped; L2 = shared, configurable |
| Connection Pool | HikariCP (Spring Boot default) — fast, lightweight |
