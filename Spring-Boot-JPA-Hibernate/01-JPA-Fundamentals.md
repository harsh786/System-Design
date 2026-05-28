# JPA Fundamentals - Interview Questions & Answers

---

## Q1: What is JPA? How is it different from JDBC?

**JPA (Java Persistence API)** is a specification that defines how to manage relational data in Java applications. It provides an object-relational mapping (ORM) approach to interact with databases using Java objects instead of SQL.

**JDBC (Java Database Connectivity)** is a low-level API for executing SQL statements directly against a database.

| Aspect | JPA | JDBC |
|--------|-----|------|
| Abstraction Level | High (works with objects) | Low (works with SQL) |
| SQL Writing | Auto-generated (mostly) | Manual |
| Caching | Built-in (L1 & L2 cache) | None |
| Portability | Database-independent | Database-specific SQL |
| Boilerplate | Minimal | Significant |
| Relationships | Annotations (`@OneToMany`, etc.) | Manual JOIN queries |

```java
// JDBC approach
Connection conn = DriverManager.getConnection(url, user, pass);
PreparedStatement ps = conn.prepareStatement("SELECT * FROM employee WHERE id = ?");
ps.setInt(1, 1);
ResultSet rs = ps.executeQuery();
if (rs.next()) {
    Employee emp = new Employee();
    emp.setId(rs.getInt("id"));
    emp.setName(rs.getString("name"));
}

// JPA approach
Employee emp = entityManager.find(Employee.class, 1);
```

---

## Q2: What is ORM? Why do we need it?

**ORM (Object-Relational Mapping)** is a technique that maps Java objects to database tables, bridging the "impedance mismatch" between object-oriented programming and relational databases.

**Why we need ORM:**

1. **Impedance Mismatch** — Objects have inheritance, polymorphism, associations; relational DBs have tables, rows, foreign keys.
2. **Productivity** — Eliminates repetitive CRUD SQL and ResultSet mapping code.
3. **Maintainability** — Schema changes require fewer code changes.
4. **Database Independence** — Switch databases without rewriting queries.
5. **Caching & Optimization** — Built-in caching, lazy loading, dirty checking.

**The mismatch problems ORM solves:**
- **Granularity** — Object model can be more fine-grained than DB tables
- **Inheritance** — No direct equivalent in relational model
- **Identity** — `==` vs `.equals()` vs DB primary key
- **Associations** — Object references vs foreign keys
- **Navigation** — Traversing object graph vs JOIN queries

---

## Q3: What are the main components of JPA?

1. **Entity** — A POJO class mapped to a database table (`@Entity`)
2. **EntityManagerFactory** — Factory for creating EntityManager instances
3. **EntityManager** — Primary interface for CRUD operations and queries
4. **Persistence Unit** — Configuration defining datasource, entities, and properties
5. **JPQL (Java Persistence Query Language)** — Object-oriented query language
6. **Criteria API** — Type-safe programmatic query building
7. **Transaction** — `EntityTransaction` for managing transactions
8. **Annotations** — Metadata for mapping (`@Entity`, `@Table`, `@Column`, etc.)

```
┌─────────────────────────────────────────┐
│            Application Code             │
├─────────────────────────────────────────┤
│         EntityManager (API)             │
├─────────────────────────────────────────┤
│    JPA Provider (Hibernate/EclipseLink) │
├─────────────────────────────────────────┤
│              JDBC Driver                │
├─────────────────────────────────────────┤
│              Database                   │
└─────────────────────────────────────────┘
```

---

## Q4: What is EntityManagerFactory and EntityManager?

### EntityManagerFactory

- **Heavyweight, thread-safe** object created once per persistence unit.
- Responsible for creating `EntityManager` instances.
- Expensive to create — typically one per application.

### EntityManager

- **Lightweight, not thread-safe** — one per transaction/request.
- The primary API for persistence operations (persist, find, merge, remove).
- Manages the **Persistence Context** (a set of managed entity instances).

```java
// Creating EntityManagerFactory
EntityManagerFactory emf = Persistence.createEntityManagerFactory("myPU");

// Creating EntityManager
EntityManager em = emf.createEntityManager();

try {
    em.getTransaction().begin();
    
    Employee emp = new Employee();
    emp.setName("John");
    em.persist(emp);  // INSERT
    
    Employee found = em.find(Employee.class, 1L);  // SELECT
    found.setName("Jane");  // UPDATE (automatic dirty checking)
    
    em.remove(found);  // DELETE
    
    em.getTransaction().commit();
} finally {
    em.close();
}

// Close factory on app shutdown
emf.close();
```

**Key EntityManager methods:**
- `persist(entity)` — Make entity managed and persistent
- `find(Class, id)` — Find by primary key
- `merge(entity)` — Merge detached entity
- `remove(entity)` — Mark for deletion
- `flush()` — Synchronize persistence context with DB
- `detach(entity)` — Remove from persistence context
- `createQuery()` — Create JPQL query

---

## Q5: What is a Persistence Unit? Explain persistence.xml

A **Persistence Unit** defines a set of entity classes, their database connection, and JPA provider configuration. It is defined in `META-INF/persistence.xml`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<persistence xmlns="http://xmlns.jcp.org/xml/ns/persistence"
             version="2.2">

    <persistence-unit name="employeePU" transaction-type="RESOURCE_LOCAL">
        
        <!-- JPA Provider -->
        <provider>org.hibernate.jpa.HibernatePersistenceProvider</provider>
        
        <!-- Entity Classes (optional if scanning is enabled) -->
        <class>com.example.entity.Employee</class>
        <class>com.example.entity.Department</class>
        
        <!-- Exclude unlisted classes -->
        <exclude-unlisted-classes>true</exclude-unlisted-classes>
        
        <properties>
            <!-- JDBC Connection -->
            <property name="javax.persistence.jdbc.url" 
                      value="jdbc:mysql://localhost:3306/mydb"/>
            <property name="javax.persistence.jdbc.user" value="root"/>
            <property name="javax.persistence.jdbc.password" value="password"/>
            <property name="javax.persistence.jdbc.driver" 
                      value="com.mysql.cj.jdbc.Driver"/>
            
            <!-- Hibernate-specific -->
            <property name="hibernate.dialect" 
                      value="org.hibernate.dialect.MySQL8Dialect"/>
            <property name="hibernate.hbm2ddl.auto" value="update"/>
            <property name="hibernate.show_sql" value="true"/>
            <property name="hibernate.format_sql" value="true"/>
        </properties>
    </persistence-unit>
</persistence>
```

**Transaction types:**
- `RESOURCE_LOCAL` — Application manages transactions (standalone apps)
- `JTA` — Container manages transactions (Java EE / application servers)

> In **Spring Boot**, `persistence.xml` is typically replaced by `application.properties`/`application.yml` configuration.

---

## Q6: What is the difference between JPA and Hibernate?

| Aspect | JPA | Hibernate |
|--------|-----|-----------|
| Nature | **Specification** (set of interfaces & annotations) | **Implementation** (concrete library) |
| Package | `javax.persistence` / `jakarta.persistence` | `org.hibernate` |
| Cannot run alone | Needs a provider (Hibernate, EclipseLink, etc.) | Can run standalone |
| Query Language | JPQL | HQL (superset of JPQL) |
| Caching | Defines L2 cache API | Provides actual L2 cache implementation |
| Extra Features | Standard features only | Criteria extensions, filters, multi-tenancy, etc. |

```java
// JPA standard code (portable)
@Entity
@Table(name = "employees")
public class Employee {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
}

// Hibernate-specific (not portable)
@Entity
@org.hibernate.annotations.BatchSize(size = 10)
@org.hibernate.annotations.Where(clause = "active = true")
public class Employee { ... }
```

**Analogy:** JPA is like a Java interface; Hibernate is a class that implements it. You can swap Hibernate with EclipseLink without changing JPA code.

---

## Q7: What are the advantages of using JPA over plain JDBC?

1. **No boilerplate** — No manual ResultSet-to-Object mapping
2. **Database independence** — Switch DB by changing dialect
3. **Automatic dirty checking** — Modified managed entities are auto-updated
4. **Caching** — L1 (persistence context) and L2 (shared) cache
5. **Lazy loading** — Load associations on demand
6. **Relationship management** — `@OneToMany`, `@ManyToOne` etc.
7. **Schema generation** — Auto DDL from entity classes
8. **JPQL** — Object-oriented queries, no table/column name coupling
9. **Optimistic locking** — Built-in via `@Version`
10. **Inheritance mapping** — `SINGLE_TABLE`, `JOINED`, `TABLE_PER_CLASS`

**When JDBC might still be preferred:**
- Batch processing with millions of rows
- Complex stored procedure calls
- Performance-critical operations needing fine-grained SQL control
- Simple utility scripts with 1-2 queries

---

## Q8: Explain the JPA Entity Lifecycle States

```
         persist()
  NEW ──────────────► MANAGED
   │                    │  ▲
   │                    │  │ merge()
   │          remove()  │  │
   │                    ▼  │
   │                 REMOVED
   │                    
   │    detach()/close()/clear()
   │                    │
   │                    ▼
   └──────────────► DETACHED
```

### 1. New (Transient)
- Object created with `new` but not yet associated with a persistence context.
- Has no database representation.

```java
Employee emp = new Employee();  // TRANSIENT
emp.setName("John");
// Not tracked by EntityManager
```

### 2. Managed (Persistent)
- Associated with a persistence context.
- Changes are automatically detected and synchronized with DB on flush/commit.

```java
em.persist(emp);  // Now MANAGED
emp.setName("Jane");  // Auto-detected, will UPDATE on flush
```

### 3. Detached
- Was previously managed but persistence context is closed/cleared.
- Changes are NOT tracked.

```java
em.close();  // emp is now DETACHED
emp.setName("Bob");  // NOT tracked, won't sync to DB

// To re-attach:
Employee merged = em2.merge(emp);  // merged is MANAGED, emp stays DETACHED
```

### 4. Removed
- Scheduled for deletion from the database.
- Will be deleted on flush/commit.

```java
em.remove(emp);  // REMOVED state
// DELETE will execute on commit
```

**Key points for interviews:**
- Only **managed** entities have automatic dirty checking.
- `merge()` returns a NEW managed instance; the original remains detached.
- Calling `persist()` on a removed entity makes it managed again.

---

## Q9: What is the purpose of @Entity annotation?

`@Entity` marks a Java class as a JPA entity — a class that maps to a database table.

**Requirements for an entity class:**
1. Must have `@Entity` annotation
2. Must have a no-argument constructor (public or protected)
3. Must have an `@Id` field
4. Must not be `final` (class and methods)
5. Must be a top-level class (not inner unless static)

```java
@Entity
public class Employee {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String name;
    private double salary;
    
    // Required no-arg constructor
    public Employee() {}
    
    public Employee(String name, double salary) {
        this.name = name;
        this.salary = salary;
    }
    
    // getters and setters
}
```

**`@Entity` attributes:**
- `name` — Logical entity name used in JPQL queries (defaults to class name)

```java
@Entity(name = "EMP")
public class Employee { ... }

// In JPQL:
em.createQuery("SELECT e FROM EMP e", Employee.class);
```

---

## Q10: What is @Table annotation and when do you use it?

`@Table` specifies the database table that an entity maps to. It's optional — without it, the table name defaults to the entity/class name.

```java
@Entity
@Table(
    name = "employees",
    schema = "hr",
    catalog = "company_db",
    uniqueConstraints = {
        @UniqueConstraint(
            name = "uk_employee_email",
            columnNames = {"email"}
        ),
        @UniqueConstraint(
            name = "uk_emp_ssn",
            columnNames = {"ssn"}
        )
    },
    indexes = {
        @Index(
            name = "idx_emp_department",
            columnList = "department_id, last_name"
        )
    }
)
public class Employee {
    @Id
    private Long id;
    
    private String email;
    private String ssn;
    
    @Column(name = "department_id")
    private Long departmentId;
    
    @Column(name = "last_name")
    private String lastName;
}
```

**When to use `@Table`:**
- Table name differs from class name
- Table is in a specific schema/catalog
- You need to define unique constraints or indexes at the table level
- Mapping to a legacy database with non-standard naming

---

## Q11: What is @Id annotation? How do you define primary keys?

`@Id` designates the primary key field of an entity.

### Simple Primary Key

```java
@Entity
public class Employee {
    @Id
    private Long id;
}
```

### Composite Primary Key — `@IdClass`

```java
// Primary key class
public class EmployeeId implements Serializable {
    private Long departmentId;
    private Long employeeNumber;
    
    // Must override equals() and hashCode()
    @Override
    public boolean equals(Object o) { ... }
    
    @Override
    public int hashCode() { ... }
}

@Entity
@IdClass(EmployeeId.class)
public class Employee {
    @Id
    private Long departmentId;
    
    @Id
    private Long employeeNumber;
    
    private String name;
}

// Usage
EmployeeId pk = new EmployeeId(1L, 100L);
Employee emp = em.find(Employee.class, pk);
```

### Composite Primary Key — `@EmbeddedId`

```java
@Embeddable
public class EmployeeId implements Serializable {
    private Long departmentId;
    private Long employeeNumber;
    
    // equals() and hashCode()
}

@Entity
public class Employee {
    @EmbeddedId
    private EmployeeId id;
    
    private String name;
}

// Usage
EmployeeId pk = new EmployeeId();
pk.setDepartmentId(1L);
pk.setEmployeeNumber(100L);
Employee emp = em.find(Employee.class, pk);
```

**Primary key class requirements:**
- Must be `Serializable`
- Must have a no-arg constructor
- Must override `equals()` and `hashCode()`

---

## Q12: Explain different ID Generation Strategies

```java
@Id
@GeneratedValue(strategy = GenerationType.XXXX)
private Long id;
```

### 1. GenerationType.AUTO (Default)

Lets the JPA provider choose the best strategy for the database.

```java
@Id
@GeneratedValue(strategy = GenerationType.AUTO)
private Long id;
```

- Hibernate 5+ defaults to TABLE strategy (can be surprising)
- Less portable than it seems — behavior varies by provider/version

### 2. GenerationType.IDENTITY

Uses database auto-increment columns.

```java
@Id
@GeneratedValue(strategy = GenerationType.IDENTITY)
private Long id;
// MySQL: AUTO_INCREMENT, SQL Server: IDENTITY, PostgreSQL: SERIAL
```

- **Pros:** Simple, widely supported
- **Cons:** Disables JDBC batch inserts (Hibernate needs the ID immediately after INSERT)

### 3. GenerationType.SEQUENCE

Uses a database sequence object.

```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "emp_seq")
@SequenceGenerator(
    name = "emp_seq",
    sequenceName = "employee_sequence",
    initialValue = 1,
    allocationSize = 50  // Pre-allocates 50 IDs at a time
)
private Long id;
```

- **Pros:** Best performance (batch inserts work), pre-allocation reduces DB round-trips
- **Cons:** Not all databases support sequences (MySQL < 8.0)
- **Recommended** for high-throughput applications

### 4. GenerationType.TABLE

Uses a dedicated table to simulate sequences.

```java
@Id
@GeneratedValue(strategy = GenerationType.TABLE, generator = "emp_gen")
@TableGenerator(
    name = "emp_gen",
    table = "id_generator",
    pkColumnName = "gen_name",
    valueColumnName = "gen_value",
    pkColumnValue = "employee_id",
    allocationSize = 50
)
private Long id;
```

- **Pros:** Portable across all databases
- **Cons:** Poor performance (row-level locking on generator table), potential bottleneck

### Comparison

| Strategy | Batch Insert | Performance | Portability |
|----------|-------------|-------------|-------------|
| IDENTITY | No | Good | High |
| SEQUENCE | Yes | Best | Medium (no MySQL <8) |
| TABLE | Yes | Worst | Highest |
| AUTO | Depends | Depends | Provider-dependent |

---

## Q13: What is @GeneratedValue annotation?

`@GeneratedValue` indicates that the primary key value is generated automatically by the persistence provider.

```java
@Id
@GeneratedValue  // Defaults to GenerationType.AUTO
private Long id;
```

**Attributes:**
- `strategy` — Generation strategy (AUTO, IDENTITY, SEQUENCE, TABLE)
- `generator` — Name of the generator (references `@SequenceGenerator` or `@TableGenerator`)

**Without `@GeneratedValue`:**
- You must assign the ID manually before calling `persist()`
- Useful for natural keys (e.g., ISBN, email)

```java
// Natural key — no @GeneratedValue
@Entity
public class Book {
    @Id
    private String isbn;  // Assigned by application
}

// Usage
Book book = new Book();
book.setIsbn("978-0-13-468599-1");  // Must set before persist
em.persist(book);
```

---

## Q14: What is @Column annotation and its attributes?

`@Column` customizes the mapping between an entity field and a database column.

```java
@Entity
public class Employee {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(
        name = "full_name",          // DB column name
        nullable = false,            // NOT NULL constraint
        length = 100,                // VARCHAR length (default 255)
        unique = true                // UNIQUE constraint
    )
    private String name;
    
    @Column(
        precision = 10,              // Total digits
        scale = 2                    // Decimal places
    )
    private BigDecimal salary;
    
    @Column(
        columnDefinition = "TEXT",   // Exact DDL type
        insertable = true,           // Include in INSERT
        updatable = false            // Exclude from UPDATE
    )
    private String bio;
    
    @Column(
        table = "employee_details"   // Secondary table
    )
    private String address;
}
```

**Key attributes:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `name` | Field name | Database column name |
| `nullable` | `true` | Allows NULL values |
| `length` | 255 | String column length |
| `unique` | `false` | Unique constraint |
| `precision` | 0 | Decimal total digits |
| `scale` | 0 | Decimal fractional digits |
| `insertable` | `true` | Include in INSERT statements |
| `updatable` | `true` | Include in UPDATE statements |
| `columnDefinition` | — | Raw DDL fragment |

**Note:** These attributes affect DDL generation only. They don't enforce validation at the Java level — use Bean Validation (`@NotNull`, `@Size`) for that.

---

## Q15: What is the difference between persist() and merge()?

### `persist()`
- Makes a **transient** entity **managed**.
- The entity instance itself becomes managed.
- Throws `EntityExistsException` if entity already has an ID that exists.
- Only works for NEW entities.

### `merge()`
- Copies the state of a **detached** entity into a **managed** copy.
- Returns a **new managed instance** (the original stays detached).
- If entity doesn't exist in DB, performs INSERT; if it exists, performs UPDATE.
- Works for both new and detached entities.

```java
// persist() example
Employee emp = new Employee();
emp.setName("John");
em.persist(emp);  // emp is now MANAGED
emp.setName("Jane");  // Tracked! Will update on flush.

// merge() example
Employee detachedEmp = getDetachedEmployee();  // From closed session
detachedEmp.setName("Updated Name");

Employee managedEmp = em.merge(detachedEmp);  // Returns NEW managed copy

detachedEmp.setName("X");  // NOT tracked (still detached)
managedEmp.setName("Y");   // Tracked (managed)

// IMPORTANT: detachedEmp != managedEmp
```

### Key Differences

| Aspect | `persist()` | `merge()` |
|--------|-------------|-----------|
| Input state | Transient only | Transient or Detached |
| Return value | `void` | Managed entity copy |
| Original object | Becomes managed | Stays detached |
| If ID exists | Exception | UPDATE |
| Cascade | `CascadeType.PERSIST` | `CascadeType.MERGE` |

### Common mistake:

```java
// WRONG — using detached instance after merge
em.merge(detachedEmp);
detachedEmp.setName("X");  // NOT saved!

// CORRECT
Employee managed = em.merge(detachedEmp);
managed.setName("X");  // Will be saved
```

---

## Q16: What is the difference between find() and getReference()?

### `find()`
- Eagerly fetches the entity from the database (or L1 cache).
- Returns `null` if entity not found.
- Always returns a fully initialized entity.

### `getReference()`
- Returns a **proxy** (lazy placeholder) without hitting the DB.
- Throws `EntityNotFoundException` when you access a property and entity doesn't exist.
- Useful when you only need a reference for setting relationships.

```java
// find() - Immediate SELECT query
Employee emp = em.find(Employee.class, 1L);
// SQL: SELECT * FROM employee WHERE id = 1
// Returns null if not found

// getReference() - No SQL until property access
Employee empRef = em.getReference(Employee.class, 1L);
// No SQL executed yet! Just a proxy.

empRef.getName();  // NOW the SQL fires
// Throws EntityNotFoundException if id=1 doesn't exist
```

### When to use `getReference()`:

```java
// Setting a foreign key without loading the parent
Department deptRef = em.getReference(Department.class, 5L);

Employee emp = new Employee();
emp.setName("John");
emp.setDepartment(deptRef);  // Only need the ID, no need to load Department
em.persist(emp);
// INSERT INTO employee (name, department_id) VALUES ('John', 5)
// No SELECT on department table!
```

| Aspect | `find()` | `getReference()` |
|--------|----------|-------------------|
| DB hit | Immediate | Deferred (lazy proxy) |
| Not found | Returns `null` | Throws `EntityNotFoundException` |
| Return type | Actual entity | Proxy |
| Use case | Need entity data | Only need FK reference |

---

## Q17: What is @Temporal annotation? When is it used?

`@Temporal` specifies how a `java.util.Date` or `java.util.Calendar` field is stored in the database.

```java
@Entity
public class Employee {
    
    @Temporal(TemporalType.DATE)      // Only date: 2024-01-15
    private Date hireDate;
    
    @Temporal(TemporalType.TIME)      // Only time: 14:30:00
    private Date shiftStart;
    
    @Temporal(TemporalType.TIMESTAMP) // Date + time: 2024-01-15 14:30:00.000
    private Date createdAt;
}
```

**TemporalType values:**
- `DATE` — `java.sql.Date` (year, month, day)
- `TIME` — `java.sql.Time` (hour, minute, second)
- `TIMESTAMP` — `java.sql.Timestamp` (date + time + nanoseconds)

### Java 8+ Date/Time API (No @Temporal needed!)

With JPA 2.2+, `java.time` types are mapped automatically:

```java
@Entity
public class Employee {
    
    private LocalDate hireDate;        // Maps to DATE
    private LocalTime shiftStart;      // Maps to TIME
    private LocalDateTime createdAt;   // Maps to TIMESTAMP
    private OffsetDateTime updatedAt;  // Maps to TIMESTAMP WITH TIMEZONE
    private Instant lastLogin;         // Maps to TIMESTAMP
}
```

**Interview tip:** `@Temporal` is largely obsolete in modern JPA. Prefer `java.time` types which are clearer and don't require the annotation.

---

## Q18: What is @Enumerated annotation? Difference between ORDINAL and STRING?

`@Enumerated` maps a Java enum to a database column.

```java
public enum Status {
    ACTIVE,    // ordinal = 0
    INACTIVE,  // ordinal = 1
    SUSPENDED  // ordinal = 2
}

@Entity
public class Employee {
    
    @Enumerated(EnumType.ORDINAL)  // Default — stores 0, 1, 2
    private Status status;
    
    @Enumerated(EnumType.STRING)   // Stores "ACTIVE", "INACTIVE", "SUSPENDED"
    private Status accountStatus;
}
```

### ORDINAL vs STRING

| Aspect | ORDINAL | STRING |
|--------|---------|--------|
| Storage | Integer (0, 1, 2...) | String ("ACTIVE"...) |
| Space | Less (int column) | More (varchar column) |
| Readability | Poor (what is 2?) | Good |
| Refactor-safe | **NO** — reordering breaks data | Yes |
| Adding values | Safe only at end | Safe anywhere |

### Why STRING is almost always preferred:

```java
// Original enum
public enum Status {
    ACTIVE,    // 0
    INACTIVE   // 1
}

// After adding PENDING in the middle:
public enum Status {
    ACTIVE,    // 0
    PENDING,   // 1 ← BREAKS! Old "INACTIVE" rows now map to PENDING
    INACTIVE   // 2
}
```

**Best practice:** Always use `EnumType.STRING` unless you have a strong reason not to.

### Alternative: Custom converter (JPA 2.1+)

```java
@Converter(autoApply = true)
public class StatusConverter implements AttributeConverter<Status, String> {
    
    @Override
    public String convertToDatabaseColumn(Status status) {
        return status == null ? null : status.getCode();  // Custom DB value
    }
    
    @Override
    public Status convertToEntityAttribute(String code) {
        return Status.fromCode(code);
    }
}
```

---

## Q19: What are @Transient and transient keyword differences?

Both exclude a field from persistence, but they work differently.

### `transient` keyword (Java)

- Excludes from **both** JPA persistence and Java serialization.
- It's a Java language keyword.

### `@Transient` annotation (JPA)

- Excludes from JPA persistence only.
- The field **can still be serialized**.

```java
@Entity
public class Employee {
    
    @Id
    private Long id;
    private String name;
    
    @Transient
    private int age;  // Not persisted, but IS serialized
    
    transient private double tempCalculation;  // Not persisted, NOT serialized
    
    @Transient
    private String displayName;  // Computed field, not in DB, but serializable
}
```

### Comparison

| Aspect | `@Transient` | `transient` keyword |
|--------|-------------|---------------------|
| Persistence | Excluded | Excluded |
| Serialization | Included | Excluded |
| Type | JPA annotation | Java keyword |
| Use case | Computed fields you want to serialize (e.g., JSON response) | Truly temporary data |

### Practical example:

```java
@Entity
public class User {
    @Id
    private Long id;
    
    private String firstName;
    private String lastName;
    
    @Transient
    private String fullName;  // Not in DB, but included in JSON serialization
    
    @PostLoad  // JPA callback
    public void computeFullName() {
        this.fullName = firstName + " " + lastName;
    }
    
    transient private EntityManager em;  // Never persist or serialize this
}
```

---

## Q20: What is @Basic annotation? Explain FetchType.LAZY vs EAGER.

`@Basic` is the simplest mapping annotation — it maps a field to a column directly. It's **implicit** for all non-relationship fields (you rarely need to write it explicitly).

```java
@Entity
public class Employee {
    
    @Basic  // Implied — you don't need to write this
    private String name;
    
    @Basic(fetch = FetchType.LAZY, optional = false)
    @Column(columnDefinition = "TEXT")
    private String biography;  // Large text loaded lazily
    
    @Basic(fetch = FetchType.LAZY)
    @Lob
    private byte[] profilePhoto;  // Large binary loaded lazily
}
```

**`@Basic` attributes:**
- `fetch` — `FetchType.EAGER` (default) or `FetchType.LAZY`
- `optional` — Whether the field can be null (default `true`)

### FetchType.EAGER vs FetchType.LAZY

| Aspect | EAGER | LAZY |
|--------|-------|------|
| When loaded | Immediately with parent entity | On first access |
| Default for | `@Basic`, `@ManyToOne`, `@OneToOne` | `@OneToMany`, `@ManyToMany` |
| Performance | Can cause unnecessary data loading | Better for large/rarely-used fields |
| N+1 risk | Less | More (if not careful) |

```java
@Entity
public class Employee {
    
    @ManyToOne(fetch = FetchType.LAZY)  // Override default EAGER
    private Department department;
    
    @OneToMany(fetch = FetchType.LAZY)  // Default
    private List<Task> tasks;
    
    @Basic(fetch = FetchType.LAZY)
    @Lob
    private byte[] resume;  // Only load when accessed
}
```

### Important notes on `@Basic(fetch = LAZY)`:

- **Lazy loading on basic fields requires bytecode enhancement** (not just a proxy like relationships).
- Without enhancement, the provider may ignore `LAZY` and load eagerly.
- Hibernate requires `hibernate-enhance-maven-plugin` for basic field lazy loading.

```xml
<!-- Maven plugin for Hibernate bytecode enhancement -->
<plugin>
    <groupId>org.hibernate.orm.tooling</groupId>
    <artifactId>hibernate-enhance-maven-plugin</artifactId>
    <configuration>
        <enableLazyInitialization>true</enableLazyInitialization>
    </configuration>
</plugin>
```

### Common interview follow-up: LazyInitializationException

```java
Employee emp = em.find(Employee.class, 1L);
em.close();  // Persistence context closed

emp.getDepartment().getName();  // LazyInitializationException!
// The proxy can't load data — no active session

// Solutions:
// 1. Access within open session
// 2. Use JOIN FETCH in JPQL
// 3. Use @EntityGraph
// 4. Open Session in View pattern (anti-pattern in many cases)
```

---

## Summary Cheat Sheet

| Annotation | Purpose |
|-----------|---------|
| `@Entity` | Marks class as JPA entity |
| `@Table` | Customizes table mapping |
| `@Id` | Defines primary key |
| `@GeneratedValue` | Auto-generates PK values |
| `@Column` | Customizes column mapping |
| `@Basic` | Simplest field mapping (implicit) |
| `@Temporal` | Date/time precision (legacy) |
| `@Enumerated` | Enum storage strategy |
| `@Transient` | Exclude from persistence |
| `@Lob` | Large object (BLOB/CLOB) |

---
