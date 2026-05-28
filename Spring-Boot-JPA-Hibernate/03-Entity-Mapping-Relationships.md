# Entity Mapping & Relationships - Interview Questions (Q41-Q65)

---

## Q41: Explain @OneToOne mapping with example

**Answer:** `@OneToOne` defines a single-valued association where one entity instance is associated with exactly one instance of another entity.

```java
@Entity
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String username;

    @OneToOne(cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @JoinColumn(name = "profile_id", referencedColumnName = "id")
    private UserProfile profile;
}

@Entity
public class UserProfile {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String bio;
    private String avatarUrl;

    @OneToOne(mappedBy = "profile")
    private User user;
}
```

**Key points:**
- The `@JoinColumn` side is the **owning side** (has the FK column).
- The `mappedBy` side is the **inverse side**.
- Use `FetchType.LAZY` to avoid unnecessary joins.
- Shared primary key approach using `@MapsId` is often preferred for true 1:1.

**Shared Primary Key variant:**
```java
@Entity
public class UserProfile {
    @Id
    private Long id; // same as User's PK

    @OneToOne
    @MapsId
    @JoinColumn(name = "id")
    private User user;
}
```

---

## Q42: Explain @OneToMany and @ManyToOne mapping

**Answer:** This is the most common relationship in JPA. One parent entity has many child entities.

```java
@Entity
public class Department {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;

    @OneToMany(mappedBy = "department", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Employee> employees = new ArrayList<>();

    // Helper methods for bidirectional sync
    public void addEmployee(Employee emp) {
        employees.add(emp);
        emp.setDepartment(this);
    }

    public void removeEmployee(Employee emp) {
        employees.remove(emp);
        emp.setDepartment(null);
    }
}

@Entity
public class Employee {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    private Department department;
}
```

**Key points:**
- `@ManyToOne` is always the **owning side** (holds the FK).
- `@OneToMany` with `mappedBy` is the inverse side.
- Always use `FetchType.LAZY` on `@ManyToOne` (it defaults to EAGER).
- Avoid unidirectional `@OneToMany` without `mappedBy` — it uses a join table by default and is less efficient.
- Always define helper methods to keep both sides in sync.

---

## Q43: Explain @ManyToMany mapping with join table

**Answer:** `@ManyToMany` creates an association where multiple instances of one entity relate to multiple instances of another, implemented via a join/junction table.

```java
@Entity
public class Student {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;

    @ManyToMany(cascade = {CascadeType.PERSIST, CascadeType.MERGE})
    @JoinTable(
        name = "student_course",
        joinColumns = @JoinColumn(name = "student_id"),
        inverseJoinColumns = @JoinColumn(name = "course_id")
    )
    private Set<Course> courses = new HashSet<>();
}

@Entity
public class Course {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String title;

    @ManyToMany(mappedBy = "courses")
    private Set<Student> students = new HashSet<>();
}
```

**When the join table has extra columns**, promote it to an entity:

```java
@Entity
@Table(name = "enrollment")
public class Enrollment {
    @EmbeddedId
    private EnrollmentId id;

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("studentId")
    private Student student;

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("courseId")
    private Course course;

    private LocalDate enrolledDate;
    private String grade;
}

@Embeddable
public class EnrollmentId implements Serializable {
    private Long studentId;
    private Long courseId;
    // equals() and hashCode()
}
```

**Best practices:**
- Use `Set` instead of `List` to avoid duplicate bag issues.
- Never use `CascadeType.REMOVE` on `@ManyToMany`.
- Prefer the explicit join entity approach for non-trivial associations.

---

## Q44: What is the owning side vs inverse side of a relationship?

**Answer:** In a bidirectional relationship, JPA needs to know which side is responsible for managing the foreign key column in the database.

| Aspect | Owning Side | Inverse Side |
|--------|-------------|--------------|
| FK management | Controls the FK column | Does not manage FK |
| Annotation | Has `@JoinColumn` | Has `mappedBy` |
| Persistence | Changes here are persisted to DB | Changes here are **ignored** by JPA |
| Required? | Yes, always required | Optional (for navigation only) |

**Rules:**
- `@ManyToOne` is always the owning side.
- In `@OneToOne`, the side with `@JoinColumn` is the owner.
- In `@ManyToMany`, the side with `@JoinTable` is the owner.

**Common mistake:**
```java
// This does NOT persist the relationship!
department.getEmployees().add(employee);

// This DOES persist it (owning side):
employee.setDepartment(department);
```

Always update **both sides** of a bidirectional relationship to keep the in-memory model consistent.

---

## Q45: What is mappedBy attribute? When do you use it?

**Answer:** `mappedBy` declares the inverse (non-owning) side of a bidirectional relationship. Its value is the field name on the owning entity that maps back.

```java
@Entity
public class Post {
    @Id
    private Long id;

    @OneToMany(mappedBy = "post") // "post" = field name in Comment entity
    private List<Comment> comments;
}

@Entity
public class Comment {
    @Id
    private Long id;

    @ManyToOne
    @JoinColumn(name = "post_id")
    private Post post; // This is the owning side
}
```

**When to use:**
- Always on the inverse side of a bidirectional relationship.
- On `@OneToMany` pointing to the `@ManyToOne` field.
- On one side of `@OneToOne` and `@ManyToMany`.

**Without `mappedBy`**, JPA treats both sides as separate unidirectional relationships, potentially creating an extra join table.

---

## Q46: What is CascadeType? Explain all cascade types

**Answer:** `CascadeType` propagates entity state transitions (lifecycle operations) from a parent entity to its associated child entities.

| Cascade Type | Description |
|-------------|-------------|
| `PERSIST` | When parent is persisted, children are also persisted |
| `MERGE` | When parent is merged, children are also merged |
| `REMOVE` | When parent is removed, children are also removed |
| `REFRESH` | When parent is refreshed from DB, children are also refreshed |
| `DETACH` | When parent is detached from persistence context, children are also detached |
| `ALL` | All of the above combined |

```java
@Entity
public class Order {
    @Id
    private Long id;

    // Cascade persist and merge but not remove
    @OneToMany(mappedBy = "order", cascade = {CascadeType.PERSIST, CascadeType.MERGE})
    private List<OrderItem> items = new ArrayList<>();
}

// CascadeType.ALL example
@Entity
public class Post {
    @OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Comment> comments = new ArrayList<>();
}
```

**Best practices:**
- Use `CascadeType.ALL` only for true parent-child (composition) relationships.
- Never use `CascadeType.REMOVE` or `ALL` on `@ManyToMany`.
- `PERSIST` + `MERGE` is the safest combination for most use cases.
- Be careful with `REMOVE` — it can unintentionally delete shared entities.

---

## Q47: What is orphanRemoval? How is it different from CascadeType.REMOVE?

**Answer:**

| Feature | `CascadeType.REMOVE` | `orphanRemoval = true` |
|---------|----------------------|------------------------|
| Trigger | Parent entity is deleted | Child is removed from parent's collection OR parent is deleted |
| Scope | Only on parent deletion | Also when child is disassociated |
| Use case | Delete children when parent dies | Delete children that no longer belong to any parent |

```java
@Entity
public class Post {
    @OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Comment> comments = new ArrayList<>();
}

// With orphanRemoval = true:
post.getComments().remove(comment); // comment is DELETED from DB
post.getComments().clear();         // all comments are DELETED from DB

// With only CascadeType.REMOVE (no orphanRemoval):
post.getComments().remove(comment); // comment is NOT deleted, just disassociated
entityManager.remove(post);         // now comments ARE deleted (cascade)
```

**Key point:** `orphanRemoval` implies `CascadeType.REMOVE` behavior but goes further — it also deletes entities that are simply removed from the collection.

---

## Q48: What is FetchType.LAZY vs FetchType.EAGER in relationships?

**Answer:**

| FetchType | Behavior | When data is loaded |
|-----------|----------|---------------------|
| `LAZY` | Proxy/placeholder is created | On first access of the association |
| `EAGER` | Loaded immediately with parent | At query time via JOIN or subselect |

**Defaults:**
- `@OneToOne` → EAGER
- `@ManyToOne` → EAGER
- `@OneToMany` → LAZY
- `@ManyToMany` → LAZY

```java
@ManyToOne(fetch = FetchType.LAZY) // Override default EAGER
@JoinColumn(name = "department_id")
private Department department;

@OneToMany(mappedBy = "post", fetch = FetchType.LAZY) // Already default
private List<Comment> comments;
```

**LAZY pitfalls:**
- `LazyInitializationException` — accessing a lazy association outside an open session/transaction.
- N+1 problem — loading a collection triggers N additional queries.

**Solutions for N+1:**
```java
// 1. JOIN FETCH in JPQL
@Query("SELECT p FROM Post p JOIN FETCH p.comments WHERE p.id = :id")
Post findWithComments(@Param("id") Long id);

// 2. @EntityGraph
@EntityGraph(attributePaths = {"comments"})
Optional<Post> findById(Long id);

// 3. @BatchSize (Hibernate)
@BatchSize(size = 25)
@OneToMany(mappedBy = "post")
private List<Comment> comments;
```

**Best practice:** Always use LAZY and fetch eagerly only when needed via JOIN FETCH or EntityGraph.

---

## Q49: What is @JoinColumn annotation?

**Answer:** `@JoinColumn` specifies the foreign key column used to join an entity association or element collection.

```java
@Entity
public class Employee {
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(
        name = "dept_id",                    // FK column name in this table
        referencedColumnName = "id",         // PK column in target table (default: PK)
        nullable = false,                    // NOT NULL constraint
        unique = false,                      // UNIQUE constraint
        insertable = true,                   // Include in INSERT statements
        updatable = true,                    // Include in UPDATE statements
        columnDefinition = "BIGINT",         // DDL column definition
        foreignKey = @ForeignKey(name = "FK_EMP_DEPT") // FK constraint name
    )
    private Department department;
}
```

**Composite FK with multiple @JoinColumn:**
```java
@ManyToOne
@JoinColumns({
    @JoinColumn(name = "country_code", referencedColumnName = "code"),
    @JoinColumn(name = "country_name", referencedColumnName = "name")
})
private Country country;
```

---

## Q50: What is @JoinTable annotation?

**Answer:** `@JoinTable` specifies the join/junction table for `@ManyToMany` or unidirectional `@OneToMany` relationships.

```java
@ManyToMany
@JoinTable(
    name = "user_role",                                    // Join table name
    joinColumns = @JoinColumn(name = "user_id"),          // FK to owning entity
    inverseJoinColumns = @JoinColumn(name = "role_id"),   // FK to inverse entity
    uniqueConstraints = @UniqueConstraint(columnNames = {"user_id", "role_id"}),
    indexes = @Index(columnList = "role_id")
)
private Set<Role> roles = new HashSet<>();
```

**Generated table:**
```sql
CREATE TABLE user_role (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
```

---

## Q51: Explain bidirectional vs unidirectional relationships

**Answer:**

**Unidirectional** — only one entity has a reference to the other:
```java
@Entity
public class Order {
    @ManyToOne
    @JoinColumn(name = "customer_id")
    private Customer customer;  // Order knows about Customer
}

@Entity
public class Customer {
    @Id
    private Long id;
    // No reference to Order — cannot navigate from Customer to Orders
}
```

**Bidirectional** — both entities reference each other:
```java
@Entity
public class Customer {
    @OneToMany(mappedBy = "customer")
    private List<Order> orders; // Can navigate both ways
}

@Entity
public class Order {
    @ManyToOne
    @JoinColumn(name = "customer_id")
    private Customer customer;
}
```

| Aspect | Unidirectional | Bidirectional |
|--------|---------------|---------------|
| Navigation | One way only | Both directions |
| Complexity | Simpler | More complex (sync both sides) |
| Queries | Need explicit joins | Can traverse from either side |
| Performance | Potentially extra join table for @OneToMany | More efficient with mappedBy |

**Recommendation:** Start unidirectional; add the inverse side only when you need navigability from both directions.

---

## Q52: What is @Embeddable and @Embedded?

**Answer:** `@Embeddable` defines a class whose instances are stored as part of the owning entity's table (no separate table, no own identity).

```java
@Embeddable
public class Address {
    private String street;
    private String city;
    private String state;

    @Column(name = "zip_code")
    private String zipCode;
}

@Entity
public class Employee {
    @Id
    private Long id;
    private String name;

    @Embedded
    private Address homeAddress;

    @Embedded
    @AttributeOverrides({
        @AttributeOverride(name = "street", column = @Column(name = "office_street")),
        @AttributeOverride(name = "city", column = @Column(name = "office_city")),
        @AttributeOverride(name = "state", column = @Column(name = "office_state")),
        @AttributeOverride(name = "zipCode", column = @Column(name = "office_zip"))
    })
    private Address officeAddress;
}
```

**Generated table:**
```sql
CREATE TABLE employee (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255),
    street VARCHAR(255),        -- homeAddress
    city VARCHAR(255),
    state VARCHAR(255),
    zip_code VARCHAR(255),
    office_street VARCHAR(255), -- officeAddress
    office_city VARCHAR(255),
    office_state VARCHAR(255),
    office_zip VARCHAR(255)
);
```

**Use cases:** Value objects (Address, Money, DateRange) that have no identity of their own.

---

## Q53: What is @ElementCollection?

**Answer:** `@ElementCollection` maps a collection of basic types or embeddable objects. Unlike `@OneToMany`, the elements have no identity and are always owned by the parent.

```java
@Entity
public class User {
    @Id
    private Long id;

    // Collection of basic types
    @ElementCollection
    @CollectionTable(name = "user_phones", joinColumns = @JoinColumn(name = "user_id"))
    @Column(name = "phone_number")
    private Set<String> phoneNumbers = new HashSet<>();

    // Collection of embeddables
    @ElementCollection(fetch = FetchType.LAZY)
    @CollectionTable(name = "user_addresses", joinColumns = @JoinColumn(name = "user_id"))
    private List<Address> addresses = new ArrayList<>();
}
```

**Key differences from @OneToMany:**

| Feature | @ElementCollection | @OneToMany |
|---------|-------------------|------------|
| Target type | Basic/Embeddable | Entity |
| Own table | Yes (collection table) | Yes (entity table) |
| Own identity | No | Yes (has @Id) |
| Lifecycle | Fully dependent on parent | Can exist independently |
| Cascade | Implicit (always cascaded) | Explicit via CascadeType |

**Limitation:** Updating a single element often results in deleting all rows and re-inserting. For large collections, prefer `@OneToMany` with an entity.

---

## Q54: What is @MappedSuperclass?

**Answer:** `@MappedSuperclass` defines a base class whose fields are mapped to the child entity's table. It is **not** an entity itself — no separate table, cannot be queried directly.

```java
@MappedSuperclass
public abstract class BaseEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    private LocalDateTime updatedAt;

    @Version
    private Integer version;
}

@Entity
@Table(name = "products")
public class Product extends BaseEntity {
    private String name;
    private BigDecimal price;
}

@Entity
@Table(name = "orders")
public class Order extends BaseEntity {
    private String orderNumber;
    private BigDecimal total;
}
```

**Key points:**
- Cannot use `@MappedSuperclass` in JPQL queries (e.g., `SELECT b FROM BaseEntity b` is invalid).
- No `@Entity` or `@Table` on the superclass.
- Each subclass gets its own table containing all inherited + own columns.
- Ideal for sharing audit fields (id, createdAt, updatedAt, version).

---

## Q55: Explain inheritance mapping strategies (SINGLE_TABLE, JOINED, TABLE_PER_CLASS)

**Answer:**

### 1. SINGLE_TABLE (Default)

All classes in the hierarchy map to **one table** with a discriminator column.

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(name = "payment_type", discriminatorType = DiscriminatorType.STRING)
public abstract class Payment {
    @Id @GeneratedValue
    private Long id;
    private BigDecimal amount;
}

@Entity
@DiscriminatorValue("CREDIT_CARD")
public class CreditCardPayment extends Payment {
    private String cardNumber;
    private String expiryDate;
}

@Entity
@DiscriminatorValue("BANK_TRANSFER")
public class BankTransferPayment extends Payment {
    private String bankName;
    private String accountNumber;
}
```

| Pros | Cons |
|------|------|
| Best performance (no joins) | Subclass columns must be nullable |
| Simple queries | Table can become wide/sparse |
| Polymorphic queries are fast | No NOT NULL on subclass fields |

### 2. JOINED

Each class has its own table; queries use JOINs.

```java
@Entity
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class Payment {
    @Id @GeneratedValue
    private Long id;
    private BigDecimal amount;
}

@Entity
@PrimaryKeyJoinColumn(name = "payment_id")
public class CreditCardPayment extends Payment {
    private String cardNumber; // Can be NOT NULL
}
```

| Pros | Cons |
|------|------|
| Normalized schema | Slower (requires JOINs) |
| Subclass columns can be NOT NULL | Complex queries for deep hierarchies |
| No wasted space | Insert requires multiple tables |

### 3. TABLE_PER_CLASS

Each concrete class has its own **complete** table (including inherited fields).

```java
@Entity
@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)
public abstract class Payment {
    @Id @GeneratedValue(strategy = GenerationType.TABLE) // IDENTITY won't work
    private Long id;
    private BigDecimal amount;
}
```

| Pros | Cons |
|------|------|
| No joins for concrete queries | Polymorphic queries use UNION ALL (slow) |
| Each table is self-contained | Duplicate columns across tables |
| Good isolation | Cannot use IDENTITY generation |

**Summary:**
- Use **SINGLE_TABLE** for simple hierarchies with few subclass-specific columns.
- Use **JOINED** when data integrity (NOT NULL) is important.
- Avoid **TABLE_PER_CLASS** unless you rarely query polymorphically.

---

## Q56: What is @DiscriminatorColumn and @DiscriminatorValue?

**Answer:** Used with `SINGLE_TABLE` and `JOINED` inheritance to distinguish between entity types in the same table.

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(
    name = "vehicle_type",                          // Column name
    discriminatorType = DiscriminatorType.STRING,    // STRING, INTEGER, CHAR
    length = 30                                     // Column length
)
@DiscriminatorValue("VEHICLE")  // Value for the base class (if not abstract)
public abstract class Vehicle {
    @Id @GeneratedValue
    private Long id;
    private String manufacturer;
}

@Entity
@DiscriminatorValue("CAR")
public class Car extends Vehicle {
    private int numberOfDoors;
}

@Entity
@DiscriminatorValue("TRUCK")
public class Truck extends Vehicle {
    private double payloadCapacity;
}
```

**Generated table:**
```sql
CREATE TABLE vehicle (
    id BIGINT PRIMARY KEY,
    vehicle_type VARCHAR(30),   -- discriminator
    manufacturer VARCHAR(255),
    number_of_doors INT,        -- Car only
    payload_capacity DOUBLE     -- Truck only
);
```

**Hibernate-specific:** Use `@DiscriminatorFormula` for computed discriminator values based on SQL expressions.

---

## Q57: What is @SecondaryTable?

**Answer:** `@SecondaryTable` maps a single entity to **multiple tables**.

```java
@Entity
@Table(name = "employee")
@SecondaryTable(
    name = "employee_detail",
    pkJoinColumns = @PrimaryKeyJoinColumn(name = "emp_id", referencedColumnName = "id")
)
public class Employee {
    @Id @GeneratedValue
    private Long id;
    private String name;          // In "employee" table

    @Column(table = "employee_detail")
    private String biography;     // In "employee_detail" table

    @Column(table = "employee_detail")
    private String linkedinUrl;   // In "employee_detail" table
}
```

**Use cases:**
- Mapping to a legacy schema with split tables.
- Separating frequently accessed columns from rarely accessed ones.
- Mapping to database views alongside the main table.

Multiple secondary tables:
```java
@SecondaryTables({
    @SecondaryTable(name = "employee_detail"),
    @SecondaryTable(name = "employee_audit")
})
```

---

## Q58: What is @OrderBy and @OrderColumn?

**Answer:**

### @OrderBy (JPA)

Specifies the ordering when a collection is loaded. Uses JPQL property names.

```java
@OneToMany(mappedBy = "post")
@OrderBy("createdAt DESC, id ASC")
private List<Comment> comments;

@ElementCollection
@OrderBy  // Default: orders by PK ascending
private List<String> tags;
```

This adds `ORDER BY` to the SQL query. No extra column is stored.

### @OrderColumn (JPA)

Persists the `List` index as a separate column in the database, maintaining insertion order.

```java
@OneToMany(mappedBy = "chapter")
@OrderColumn(name = "chapter_order")
private List<Page> pages;
```

**Generated column:**
```sql
ALTER TABLE page ADD COLUMN chapter_order INT;
```

| Feature | @OrderBy | @OrderColumn |
|---------|----------|--------------|
| Storage | No extra column | Adds index column |
| Ordering | By entity property | By list position |
| Mutable order | No (derived from data) | Yes (reorderable) |
| Performance | Sorting at query time | Direct indexed access |

---

## Q59: What is @Lob annotation?

**Answer:** `@Lob` marks a field as a Large Object — either CLOB (character) or BLOB (binary) based on the Java type.

```java
@Entity
public class Document {
    @Id @GeneratedValue
    private Long id;

    @Lob
    @Column(columnDefinition = "TEXT")
    private String content;       // Maps to CLOB/TEXT

    @Lob
    @Basic(fetch = FetchType.LAZY)
    private byte[] fileData;      // Maps to BLOB/BYTEA

    @Lob
    private char[] largeText;     // Maps to CLOB
}
```

**Type mapping:**
- `String`, `char[]`, `Character[]` → CLOB
- `byte[]`, `Byte[]`, `Serializable` → BLOB

**Best practice:** Use `@Basic(fetch = FetchType.LAZY)` on LOB fields to avoid loading large data unnecessarily. Note: bytecode enhancement may be required for lazy basic fields to work.

---

## Q60: What is @Formula annotation in Hibernate?

**Answer:** `@Formula` is a Hibernate-specific annotation that maps a field to a SQL expression (computed/derived column). It is read-only and evaluated on every query.

```java
@Entity
public class Order {
    @Id @GeneratedValue
    private Long id;
    private BigDecimal subtotal;
    private BigDecimal taxRate;

    @Formula("subtotal * (1 + tax_rate)")
    private BigDecimal totalAmount;

    @Formula("(SELECT COUNT(*) FROM order_item oi WHERE oi.order_id = id)")
    private int itemCount;

    @Formula("DATEDIFF(CURRENT_DATE, created_at)")
    private int daysSinceCreated;
}
```

**Key points:**
- Uses **SQL column names**, not Java field names.
- Read-only — cannot be used in INSERT/UPDATE.
- Evaluated every time the entity is loaded (SQL subselect).
- Useful for calculated fields without denormalization.
- Not portable across databases if using DB-specific functions.

---

## Q61: Explain composite primary keys (@IdClass vs @EmbeddedId)

**Answer:** Both approaches define a composite primary key. The PK class must implement `Serializable`, override `equals()` and `hashCode()`, and have a no-arg constructor.

### @IdClass Approach

```java
// PK class
public class EmployeeId implements Serializable {
    private Long companyId;
    private Long employeeNumber;

    // no-arg constructor, equals(), hashCode()
}

@Entity
@IdClass(EmployeeId.class)
public class Employee {
    @Id
    private Long companyId;

    @Id
    private Long employeeNumber;

    private String name;
}

// Usage
Employee emp = entityManager.find(Employee.class, new EmployeeId(1L, 100L));
```

### @EmbeddedId Approach

```java
@Embeddable
public class EmployeeId implements Serializable {
    private Long companyId;
    private Long employeeNumber;

    // no-arg constructor, equals(), hashCode()
}

@Entity
public class Employee {
    @EmbeddedId
    private EmployeeId id;

    private String name;
}

// Usage
Employee emp = entityManager.find(Employee.class, new EmployeeId(1L, 100L));

// JPQL difference
// @IdClass:     SELECT e.companyId FROM Employee e
// @EmbeddedId:  SELECT e.id.companyId FROM Employee e
```

| Feature | @IdClass | @EmbeddedId |
|---------|----------|-------------|
| Field access | Direct (`e.companyId`) | Via embedded (`e.id.companyId`) |
| JPQL style | Flat | Nested |
| PK class annotation | Plain class | @Embeddable |
| Reusability | Less reusable | More reusable as value object |
| HQL/Criteria | Slightly simpler | More OO |

---

## Q62: What is @MapsId annotation?

**Answer:** `@MapsId` maps a relationship's foreign key as the entity's primary key (or part of a composite PK). It creates a shared primary key between entities.

```java
// Shared PK in @OneToOne
@Entity
public class User {
    @Id @GeneratedValue
    private Long id;
    private String username;

    @OneToOne(mappedBy = "user", cascade = CascadeType.ALL)
    private UserProfile profile;
}

@Entity
public class UserProfile {
    @Id
    private Long id;  // Same value as User's id

    @OneToOne
    @MapsId  // Maps the @Id field to the User FK
    @JoinColumn(name = "id")
    private User user;

    private String bio;
}
```

**With composite key:**
```java
@Embeddable
public class EnrollmentId implements Serializable {
    private Long studentId;
    private Long courseId;
}

@Entity
public class Enrollment {
    @EmbeddedId
    private EnrollmentId id;

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("studentId")  // Maps to the studentId field in EmbeddedId
    private Student student;

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("courseId")
    private Course course;
}
```

**Benefits:**
- Avoids redundant columns (FK serves as both PK and FK).
- More efficient schema.
- Essential for derived identifiers.

---

## Q63: What is @NaturalId in Hibernate?

**Answer:** `@NaturalId` is a Hibernate-specific annotation marking a field (or combination of fields) as a natural/business key — a unique identifier with business meaning (e.g., ISBN, email, SSN).

```java
@Entity
public class Book {
    @Id @GeneratedValue
    private Long id;

    @NaturalId
    @Column(nullable = false, unique = true)
    private String isbn;

    private String title;
}

@Entity
public class User {
    @Id @GeneratedValue
    private Long id;

    @NaturalId(mutable = true)  // Allow updates (e.g., email can change)
    private String email;
}
```

**Loading by natural ID:**
```java
Book book = session.byNaturalId(Book.class)
    .using("isbn", "978-0134685991")
    .load();

// With multiple natural id fields
Optional<Entity> entity = session.byNaturalId(Entity.class)
    .using("field1", value1)
    .using("field2", value2)
    .loadOptional();
```

**Benefits:**
- Hibernate caches natural ID → PK resolution (second-level cache aware).
- Avoids an extra query when you know the natural ID.
- Documents business keys in the entity model.
- Default is immutable; use `mutable = true` if the natural key can change.

---

## Q64: What are @PrePersist, @PostPersist, @PreUpdate, @PostUpdate callbacks?

**Answer:** JPA lifecycle callbacks are methods invoked automatically at specific points in an entity's lifecycle.

```java
@Entity
public class AuditableEntity {
    @Id @GeneratedValue
    private Long id;
    private String data;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private String createdBy;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        this.createdBy = SecurityContextHolder.getContext()
            .getAuthentication().getName();
    }

    @PostPersist
    protected void afterCreate() {
        log.info("Entity created with id: {}", this.id);
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    @PostUpdate
    protected void afterUpdate() {
        log.info("Entity updated: {}", this.id);
    }

    @PreRemove
    protected void onDelete() {
        log.warn("About to delete entity: {}", this.id);
    }

    @PostRemove
    protected void afterDelete() {
        log.info("Entity deleted: {}", this.id);
    }

    @PostLoad
    protected void onLoad() {
        // Called after entity is loaded from DB
    }
}
```

**All callbacks:**

| Annotation | When |
|-----------|------|
| `@PrePersist` | Before INSERT |
| `@PostPersist` | After INSERT (ID is available) |
| `@PreUpdate` | Before UPDATE |
| `@PostUpdate` | After UPDATE |
| `@PreRemove` | Before DELETE |
| `@PostRemove` | After DELETE |
| `@PostLoad` | After SELECT/loading |

**Rules:**
- Callback methods must return `void` and take no arguments.
- Avoid calling `EntityManager` inside callbacks (undefined behavior).
- Exceptions in `@Pre*` callbacks cause the operation to be rolled back.

---

## Q65: What is @EntityListeners?

**Answer:** `@EntityListeners` externalizes lifecycle callbacks into a separate listener class, promoting reusability and separation of concerns.

```java
// Listener class (not an entity)
public class AuditListener {

    @PrePersist
    public void setCreatedFields(Object entity) {
        if (entity instanceof Auditable auditable) {
            auditable.setCreatedAt(LocalDateTime.now());
            auditable.setCreatedBy(getCurrentUser());
        }
    }

    @PreUpdate
    public void setUpdatedFields(Object entity) {
        if (entity instanceof Auditable auditable) {
            auditable.setUpdatedAt(LocalDateTime.now());
            auditable.setUpdatedBy(getCurrentUser());
        }
    }

    private String getCurrentUser() {
        return SecurityContextHolder.getContext()
            .getAuthentication().getName();
    }
}

// Interface
public interface Auditable {
    void setCreatedAt(LocalDateTime time);
    void setCreatedBy(String user);
    void setUpdatedAt(LocalDateTime time);
    void setUpdatedBy(String user);
}

// Entity using the listener
@Entity
@EntityListeners(AuditListener.class)
public class Product implements Auditable {
    @Id @GeneratedValue
    private Long id;
    private String name;
    private LocalDateTime createdAt;
    private String createdBy;
    private LocalDateTime updatedAt;
    private String updatedBy;

    // getters, setters...
}
```

**Spring Data JPA's built-in audit support:**
```java
@Entity
@EntityListeners(AuditingEntityListener.class)  // Spring's listener
public class Product {
    @Id @GeneratedValue
    private Long id;

    @CreatedDate
    private LocalDateTime createdAt;

    @LastModifiedDate
    private LocalDateTime updatedAt;

    @CreatedBy
    private String createdBy;

    @LastModifiedBy
    private String updatedBy;
}

// Enable in config
@Configuration
@EnableJpaAuditing
public class JpaConfig {
    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(
            SecurityContextHolder.getContext().getAuthentication().getName()
        );
    }
}
```

**Global listeners** can be defined in `orm.xml` to apply to all entities without annotation:
```xml
<persistence-unit-metadata>
    <persistence-unit-defaults>
        <entity-listeners>
            <entity-listener class="com.example.AuditListener"/>
        </entity-listeners>
    </persistence-unit-defaults>
</persistence-unit-metadata>
```

**Multiple listeners execute in declaration order:**
```java
@EntityListeners({AuditListener.class, ValidationListener.class, NotificationListener.class})
```

---
