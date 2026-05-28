# Advanced Topics - Interview Questions (Q176-Q195)

---

## Q176: What is Multi-Tenancy in Hibernate? Explain different strategies (SCHEMA, DATABASE, DISCRIMINATOR)

**Multi-Tenancy** is an architecture where a single application instance serves multiple tenants (customers/organizations) while keeping their data isolated.

### Hibernate Multi-Tenancy Strategies:

| Strategy | Isolation | Complexity | Cost |
|----------|-----------|------------|------|
| DATABASE | Highest | High | High |
| SCHEMA | High | Medium | Medium |
| DISCRIMINATOR | Lowest | Low | Low |

### 1. DATABASE Strategy
Each tenant has a separate database:

```
Tenant A → database_tenant_a
Tenant B → database_tenant_b
```

**Pros:** Complete data isolation, easy backup/restore per tenant
**Cons:** High infrastructure cost, complex connection management

### 2. SCHEMA Strategy
Each tenant has a separate schema within the same database:

```
Same DB → schema_tenant_a, schema_tenant_b
```

**Pros:** Good isolation, shared infrastructure
**Cons:** Not all databases support schemas equally

### 3. DISCRIMINATOR (Partitioned Data)
All tenants share the same tables, distinguished by a tenant identifier column:

```sql
SELECT * FROM orders WHERE tenant_id = 'tenant_a';
```

**Pros:** Simple, low cost, easy to manage
**Cons:** Risk of data leakage, complex queries, harder to scale individual tenants

---

## Q177: How to implement Multi-Tenancy with Spring Boot and Hibernate?

### Step 1: Define Tenant Identifier Resolver

```java
@Component
public class TenantIdentifierResolver implements CurrentTenantIdentifierResolver {

    @Override
    public String resolveCurrentTenantIdentifier() {
        String tenantId = TenantContext.getCurrentTenant();
        return tenantId != null ? tenantId : "default";
    }

    @Override
    public boolean validateExistingCurrentSessions() {
        return true;
    }
}
```

### Step 2: Tenant Context (ThreadLocal)

```java
public class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();

    public static String getCurrentTenant() {
        return CURRENT_TENANT.get();
    }

    public static void setCurrentTenant(String tenant) {
        CURRENT_TENANT.set(tenant);
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
```

### Step 3: Tenant Interceptor (extract from request)

```java
@Component
public class TenantInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request,
                             HttpServletResponse response,
                             Object handler) {
        String tenantId = request.getHeader("X-Tenant-ID");
        if (tenantId != null) {
            TenantContext.setCurrentTenant(tenantId);
        }
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request,
                                HttpServletResponse response,
                                Object handler, Exception ex) {
        TenantContext.clear();
    }
}
```

### Step 4: Multi-Tenant Connection Provider (SCHEMA strategy)

```java
@Component
public class SchemaMultiTenantConnectionProvider implements MultiTenantConnectionProvider {

    @Autowired
    private DataSource dataSource;

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
        connection.createStatement()
            .execute("SET SCHEMA '" + tenantIdentifier + "'");
        return connection;
    }

    @Override
    public void releaseConnection(String tenantIdentifier, Connection connection)
            throws SQLException {
        connection.createStatement().execute("SET SCHEMA 'public'");
        releaseAnyConnection(connection);
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
        return null;
    }
}
```

### Step 5: Hibernate Configuration

```yaml
spring:
  jpa:
    properties:
      hibernate:
        multiTenancy: SCHEMA
        tenant_identifier_resolver: com.example.TenantIdentifierResolver
        multi_tenant_connection_provider: com.example.SchemaMultiTenantConnectionProvider
```

### DISCRIMINATOR Strategy (simpler approach with @Filter):

```java
@Entity
@Table(name = "orders")
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = "string"))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Order {

    @Id
    @GeneratedValue
    private Long id;

    @Column(name = "tenant_id")
    private String tenantId;

    private String description;
}
```

---

## Q178: What is Hibernate Envers? How to implement auditing/versioning?

**Hibernate Envers** (Entity Versioning System) is a Hibernate module that provides automatic auditing and versioning of entity changes. It tracks all changes (INSERT, UPDATE, DELETE) and stores historical revisions.

### Setup

**Dependency:**
```xml
<dependency>
    <groupId>org.hibernate</groupId>
    <artifactId>hibernate-envers</artifactId>
</dependency>
```

### Basic Usage

```java
@Entity
@Audited
public class Product {

    @Id
    @GeneratedValue
    private Long id;

    private String name;
    private BigDecimal price;

    @NotAudited  // exclude specific fields
    private String temporaryNote;
}
```

Envers automatically creates revision tables:
- `product_aud` — stores historical data
- `revinfo` — stores revision metadata (revision number, timestamp)

### Querying Historical Data

```java
@Service
public class AuditService {

    @PersistenceContext
    private EntityManager entityManager;

    // Get entity at a specific revision
    public Product getProductAtRevision(Long id, int revision) {
        AuditReader auditReader = AuditReaderFactory.get(entityManager);
        return auditReader.find(Product.class, id, revision);
    }

    // Get all revisions of an entity
    public List<Number> getRevisions(Long productId) {
        AuditReader auditReader = AuditReaderFactory.get(entityManager);
        return auditReader.getRevisions(Product.class, productId);
    }

    // Query audit records
    public List<Product> getProductsAtRevision(int revision) {
        AuditReader auditReader = AuditReaderFactory.get(entityManager);
        return auditReader.createQuery()
            .forEntitiesAtRevision(Product.class, revision)
            .getResultList();
    }

    // Get changes between revisions
    public List<Object[]> getChangesWithRevisionType(Long productId) {
        AuditReader auditReader = AuditReaderFactory.get(entityManager);
        return auditReader.createQuery()
            .forRevisionsOfEntity(Product.class, false, true)
            .add(AuditEntity.id().eq(productId))
            .getResultList();
        // Each Object[] contains: [entity, revisionInfo, revisionType]
    }
}
```

### Custom Revision Entity

```java
@Entity
@RevisionEntity(CustomRevisionListener.class)
@Table(name = "revinfo")
public class CustomRevisionEntity extends DefaultRevisionEntity {

    private String username;
    private String ipAddress;

    // getters/setters
}

public class CustomRevisionListener implements RevisionListener {

    @Override
    public void newRevision(Object revisionEntity) {
        CustomRevisionEntity rev = (CustomRevisionEntity) revisionEntity;
        rev.setUsername(SecurityContextHolder.getContext()
            .getAuthentication().getName());
    }
}
```

---

## Q179: What is @Audited annotation? How does revision tracking work?

### @Audited Annotation

`@Audited` marks an entity or property for automatic versioning by Hibernate Envers.

```java
@Entity
@Audited
public class Employee {
    @Id
    @GeneratedValue
    private Long id;

    private String name;
    private String department;

    @NotAudited
    private String sessionToken; // not tracked

    @Audited(targetAuditMode = RelationTargetAuditMode.NOT_AUDITED)
    @ManyToOne
    private ExternalReference ref; // relation target not audited
}
```

### How Revision Tracking Works

1. **On each transaction commit**, Envers checks if any audited entity was modified
2. If changes exist, a new **revision number** is generated (auto-increment)
3. The modified entity's state is copied to the `_AUD` table with:
   - All audited column values at that point in time
   - The revision number (foreign key to `revinfo`)
   - A `REVTYPE` column: `0` = ADD, `1` = MOD, `2` = DEL

**Generated Audit Table:**
```sql
CREATE TABLE employee_aud (
    id BIGINT NOT NULL,
    rev INTEGER NOT NULL,       -- FK to revinfo
    revtype TINYINT,            -- 0=INSERT, 1=UPDATE, 2=DELETE
    name VARCHAR(255),
    department VARCHAR(255),
    PRIMARY KEY (id, rev)
);
```

### Revision Types

```java
// Query with revision type
List<Object[]> results = auditReader.createQuery()
    .forRevisionsOfEntity(Employee.class, false, true)
    .add(AuditEntity.id().eq(employeeId))
    .addOrder(AuditEntity.revisionNumber().asc())
    .getResultList();

for (Object[] row : results) {
    Employee entity = (Employee) row[0];
    DefaultRevisionEntity revInfo = (DefaultRevisionEntity) row[1];
    RevisionType revType = (RevisionType) row[2]; // ADD, MOD, DEL
    System.out.println("Rev " + revInfo.getId() + ": " + revType + " - " + entity.getName());
}
```

### Configuration Properties

```yaml
spring:
  jpa:
    properties:
      org:
        hibernate:
          envers:
            audit_table_suffix: _audit    # default: _aud
            revision_field_name: revision  # default: rev
            store_data_at_delete: true     # store entity state on delete
            default_schema: audit          # separate schema for audit tables
```

---

## Q180: What is Hibernate Validator (Bean Validation)? Common annotations

**Hibernate Validator** is the reference implementation of the **Bean Validation** specification (JSR 380). It provides a declarative way to validate Java objects using annotations.

### Dependency (included in Spring Boot Starter Validation)

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
</dependency>
```

### Common Validation Annotations

```java
@Entity
public class User {

    @Id
    @GeneratedValue
    private Long id;

    @NotNull(message = "Name cannot be null")
    @Size(min = 2, max = 100, message = "Name must be between 2 and 100 characters")
    private String name;

    @NotBlank(message = "Email is required")
    @Email(message = "Invalid email format")
    @Column(unique = true)
    private String email;

    @Min(value = 18, message = "Age must be at least 18")
    @Max(value = 150, message = "Age must be at most 150")
    private Integer age;

    @Past(message = "Birth date must be in the past")
    private LocalDate birthDate;

    @Future(message = "Expiry date must be in the future")
    private LocalDate subscriptionExpiry;

    @Pattern(regexp = "^\\+?[1-9]\\d{1,14}$", message = "Invalid phone number")
    private String phoneNumber;

    @Positive(message = "Salary must be positive")
    @Digits(integer = 10, fraction = 2)
    private BigDecimal salary;

    @NotEmpty(message = "Roles cannot be empty")
    private List<String> roles;

    @AssertTrue(message = "Must accept terms")
    private Boolean termsAccepted;

    @URL(message = "Invalid URL")     // Hibernate-specific
    private String website;

    @CreditCardNumber                  // Hibernate-specific
    private String creditCard;

    @Length(min = 8, max = 64)         // Hibernate-specific
    private String password;
}
```

### Using in Controller

```java
@RestController
@Validated
public class UserController {

    @PostMapping("/users")
    public ResponseEntity<User> create(@Valid @RequestBody User user) {
        return ResponseEntity.ok(userService.save(user));
    }

    @GetMapping("/users")
    public List<User> search(
            @RequestParam @Min(0) int page,
            @RequestParam @Max(100) int size) {
        return userService.findAll(page, size);
    }
}
```

### Validation Groups

```java
public interface OnCreate {}
public interface OnUpdate {}

@Entity
public class Product {
    @Null(groups = OnCreate.class)
    @NotNull(groups = OnUpdate.class)
    private Long id;

    @NotBlank(groups = {OnCreate.class, OnUpdate.class})
    private String name;
}

// Usage
@PostMapping
public Product create(@Validated(OnCreate.class) @RequestBody Product p) { ... }

@PutMapping
public Product update(@Validated(OnUpdate.class) @RequestBody Product p) { ... }
```

---

## Q181: What is the difference between JPA validation and Hibernate Validator?

| Aspect | JPA Validation | Hibernate Validator (Bean Validation) |
|--------|---------------|--------------------------------------|
| **Layer** | Database/persistence layer | Application/any layer |
| **When** | At flush/commit time | Before persistence, in controllers, services |
| **Annotations** | `@Column(nullable=false, length=100)` | `@NotNull`, `@Size(max=100)` |
| **Error type** | SQL exceptions (constraint violations) | `ConstraintViolationException` (Java) |
| **Customizable** | Limited | Highly customizable |
| **Scope** | Only entities | Any Java object (DTOs, POJOs) |
| **Feedback** | Database error messages | Custom, localized messages |

### JPA Validation (Schema Constraints)

```java
@Entity
public class Product {
    @Column(nullable = false, length = 200)  // DDL constraint
    private String name;

    @Column(precision = 10, scale = 2)       // DDL constraint
    private BigDecimal price;
}
```

These generate DDL constraints but validation happens at the database level — errors arrive as SQL exceptions.

### Hibernate Validator (Bean Validation)

```java
@Entity
public class Product {
    @NotNull(message = "Name is required")
    @Size(max = 200, message = "Name too long")
    private String name;

    @DecimalMin(value = "0.01", message = "Price must be positive")
    private BigDecimal price;
}
```

Validation happens in-memory **before** SQL is generated — cleaner error handling.

### Best Practice: Use Both

```java
@Entity
public class Product {
    // Bean Validation for application-level checks
    @NotNull
    @Size(max = 200)
    // JPA for DDL generation & DB-level safety net
    @Column(nullable = false, length = 200)
    private String name;
}
```

### Disabling Auto-Validation

```yaml
spring:
  jpa:
    properties:
      javax:
        persistence:
          validation:
            mode: none  # Disable auto-validation at persist/update
```

---

## Q182: How to implement custom validators?

### Step 1: Define Custom Annotation

```java
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
@Documented
public @interface UniqueEmail {
    String message() default "Email already exists";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}
```

### Step 2: Implement ConstraintValidator

```java
@Component
public class UniqueEmailValidator implements ConstraintValidator<UniqueEmail, String> {

    @Autowired
    private UserRepository userRepository;

    @Override
    public void initialize(UniqueEmail constraintAnnotation) {
        // optional initialization
    }

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null) return true; // let @NotNull handle null
        return !userRepository.existsByEmail(email);
    }
}
```

### Step 3: Use It

```java
@Entity
public class User {
    @UniqueEmail
    @Email
    private String email;
}
```

### Class-Level Validator (Cross-Field Validation)

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = DateRangeValidator.class)
public @interface ValidDateRange {
    String message() default "End date must be after start date";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class DateRangeValidator implements ConstraintValidator<ValidDateRange, Event> {

    @Override
    public boolean isValid(Event event, ConstraintValidatorContext context) {
        if (event.getStartDate() == null || event.getEndDate() == null) {
            return true;
        }
        return event.getEndDate().isAfter(event.getStartDate());
    }
}

@Entity
@ValidDateRange
public class Event {
    private LocalDate startDate;
    private LocalDate endDate;
}
```

### Programmatic Validation

```java
@Service
public class ValidationService {

    @Autowired
    private Validator validator;

    public <T> void validate(T object) {
        Set<ConstraintViolation<T>> violations = validator.validate(object);
        if (!violations.isEmpty()) {
            String errors = violations.stream()
                .map(v -> v.getPropertyPath() + ": " + v.getMessage())
                .collect(Collectors.joining(", "));
            throw new ValidationException(errors);
        }
    }
}
```

---

## Q183: What is Flyway/Liquibase? How to use database migration with Spring Boot JPA?

**Database migration tools** manage schema evolution through versioned scripts, ensuring consistent database state across environments.

### Flyway

**Dependency:**
```xml
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
```

**Configuration:**
```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
  jpa:
    hibernate:
      ddl-auto: validate  # Don't let Hibernate manage schema
```

**Migration Scripts** (`src/main/resources/db/migration/`):

```sql
-- V1__Create_user_table.sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2__Add_role_column.sql
ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'USER';

-- V3__Create_index_on_email.sql
CREATE INDEX idx_users_email ON users(email);
```

**Naming Convention:** `V{version}__{description}.sql`
- `V1__` → Version 1
- `V1.1__` → Sub-version
- `R__` → Repeatable migration (re-run when changed)

### Liquibase

**Dependency:**
```xml
<dependency>
    <groupId>org.liquibase</groupId>
    <artifactId>liquibase-core</artifactId>
</dependency>
```

**Configuration:**
```yaml
spring:
  liquibase:
    change-log: classpath:db/changelog/db.changelog-master.yaml
```

**Changelog (YAML format):**

```yaml
# db/changelog/db.changelog-master.yaml
databaseChangeLog:
  - include:
      file: db/changelog/changes/001-create-users.yaml
  - include:
      file: db/changelog/changes/002-add-role.yaml
```

```yaml
# db/changelog/changes/001-create-users.yaml
databaseChangeLog:
  - changeSet:
      id: 1
      author: developer
      changes:
        - createTable:
            tableName: users
            columns:
              - column:
                  name: id
                  type: BIGINT
                  autoIncrement: true
                  constraints:
                    primaryKey: true
              - column:
                  name: name
                  type: VARCHAR(100)
                  constraints:
                    nullable: false
              - column:
                  name: email
                  type: VARCHAR(200)
                  constraints:
                    unique: true
                    nullable: false
```

### Flyway vs Liquibase

| Feature | Flyway | Liquibase |
|---------|--------|-----------|
| Format | SQL scripts | XML/YAML/JSON/SQL |
| Rollback | Pro only | Free (with rollback tags) |
| Diff/Generate | Pro only | Free |
| Simplicity | Simpler | More powerful but complex |
| Spring Boot | Auto-configured | Auto-configured |

### Integration with JPA

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: validate  # IMPORTANT: only validate, don't modify
    # Let Flyway/Liquibase handle schema changes
```

---

## Q184: What is @Filter and @FilterDef in Hibernate?

**Hibernate Filters** provide a way to add dynamic WHERE clauses to queries at the session level. Unlike `@Where` (static), filters can be enabled/disabled at runtime with parameters.

### Defining Filters

```java
@Entity
@Table(name = "products")
@FilterDef(name = "activeFilter",
           parameters = @ParamDef(name = "isActive", type = "boolean"))
@FilterDef(name = "priceRange",
           parameters = {
               @ParamDef(name = "minPrice", type = "big_decimal"),
               @ParamDef(name = "maxPrice", type = "big_decimal")
           })
@Filter(name = "activeFilter", condition = "active = :isActive")
@Filter(name = "priceRange", condition = "price BETWEEN :minPrice AND :maxPrice")
public class Product {

    @Id
    @GeneratedValue
    private Long id;

    private String name;
    private BigDecimal price;
    private boolean active;

    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;
}
```

### Enabling Filters

```java
@Service
public class ProductService {

    @PersistenceContext
    private EntityManager entityManager;

    public List<Product> getActiveProducts() {
        Session session = entityManager.unwrap(Session.class);

        // Enable filter with parameter
        session.enableFilter("activeFilter")
               .setParameter("isActive", true);

        return entityManager.createQuery("FROM Product", Product.class)
                            .getResultList();
        // Generated SQL will include: WHERE active = true
    }

    public List<Product> getProductsInRange(BigDecimal min, BigDecimal max) {
        Session session = entityManager.unwrap(Session.class);

        session.enableFilter("priceRange")
               .setParameter("minPrice", min)
               .setParameter("maxPrice", max);

        return entityManager.createQuery("FROM Product", Product.class)
                            .getResultList();
    }
}
```

### Filter on Collections

```java
@Entity
public class Category {

    @Id
    @GeneratedValue
    private Long id;

    @OneToMany(mappedBy = "category")
    @Filter(name = "activeFilter", condition = "active = :isActive")
    private List<Product> products;
}
```

### Aspect-Based Auto-Enabling

```java
@Aspect
@Component
public class TenantFilterAspect {

    @PersistenceContext
    private EntityManager entityManager;

    @Before("execution(* com.example.repository.*.*(..))")
    public void enableTenantFilter() {
        Session session = entityManager.unwrap(Session.class);
        session.enableFilter("tenantFilter")
               .setParameter("tenantId", TenantContext.getCurrentTenant());
    }
}
```

### @Filter vs @Where

| Feature | @Filter | @Where |
|---------|---------|--------|
| Dynamic | Yes (enable/disable) | No (always active) |
| Parameters | Yes | No |
| Runtime control | Per session | Static |
| Use case | Multi-tenancy, soft delete toggle | Always-on conditions |

---

## Q185: What is Hibernate Search? How to implement full-text search?

**Hibernate Search** integrates full-text search engines (Apache Lucene or Elasticsearch) with Hibernate ORM, providing automatic indexing and advanced search capabilities.

### Dependency

```xml
<dependency>
    <groupId>org.hibernate.search</groupId>
    <artifactId>hibernate-search-mapper-orm</artifactId>
    <version>6.2.0.Final</version>
</dependency>
<!-- For Lucene backend -->
<dependency>
    <groupId>org.hibernate.search</groupId>
    <artifactId>hibernate-search-backend-lucene</artifactId>
    <version>6.2.0.Final</version>
</dependency>
```

### Configuration

```yaml
spring:
  jpa:
    properties:
      hibernate:
        search:
          backend:
            type: lucene
            directory:
              root: ./data/search-indexes
```

### Entity Indexing

```java
@Entity
@Indexed
public class Article {

    @Id
    @GeneratedValue
    private Long id;

    @FullTextField(analyzer = "english")
    private String title;

    @FullTextField(analyzer = "english")
    private String content;

    @KeywordField
    private String category;

    @GenericField
    private LocalDate publishDate;

    @IndexedEmbedded
    @ManyToOne
    private Author author;
}

@Entity
public class Author {
    @Id
    @GeneratedValue
    private Long id;

    @FullTextField
    private String name;
}
```

### Searching

```java
@Service
public class SearchService {

    @PersistenceContext
    private EntityManager entityManager;

    public List<Article> search(String query) {
        SearchSession searchSession = Search.session(entityManager);

        SearchResult<Article> result = searchSession.search(Article.class)
            .where(f -> f.match()
                .fields("title", "content")
                .matching(query))
            .sort(f -> f.score())  // relevance
            .fetchAll();

        return result.hits();
    }

    public List<Article> advancedSearch(String text, String category,
                                         LocalDate from, LocalDate to) {
        SearchSession searchSession = Search.session(entityManager);

        return searchSession.search(Article.class)
            .where(f -> f.bool()
                .must(f.match().fields("title", "content").matching(text))
                .filter(f.match().field("category").matching(category))
                .filter(f.range().field("publishDate").between(from, to)))
            .fetchHits(20);
    }

    // Rebuild entire index
    @Transactional
    public void reindex() throws InterruptedException {
        SearchSession searchSession = Search.session(entityManager);
        searchSession.massIndexer(Article.class)
            .threadsToLoadObjects(4)
            .startAndWait();
    }
}
```

### Custom Analyzers

```java
@Entity
@Indexed
@AnalyzerDef(name = "customAnalyzer",
    tokenizer = @TokenizerDef(factory = StandardTokenizerFactory.class),
    filters = {
        @TokenFilterDef(factory = LowerCaseFilterFactory.class),
        @TokenFilterDef(factory = StopFilterFactory.class),
        @TokenFilterDef(factory = SnowballPorterFilterFactory.class,
                        params = @Parameter(name = "language", value = "English"))
    })
public class Article {
    @FullTextField(analyzer = "customAnalyzer")
    private String content;
}
```

---

## Q186: What is @Type annotation in Hibernate? Custom type mapping

`@Type` tells Hibernate how to map a Java type to a database column when the default mapping isn't sufficient.

### Common Use Cases

```java
@Entity
public class Settings {

    @Id
    @GeneratedValue
    private Long id;

    // Map Java enum to PostgreSQL enum type
    @Type(PostgreSQLEnumType.class)
    @Column(columnDefinition = "status_type")
    private Status status;

    // Store as JSON (using Vladmihalcea library)
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> metadata;

    // Binary data with specific handling
    @Type(BinaryType.class)
    private byte[] encryptedData;
}
```

### Creating a Custom Type

```java
public class EncryptedStringType implements UserType<String> {

    @Override
    public int getSqlType() {
        return Types.VARCHAR;
    }

    @Override
    public Class<String> returnedClass() {
        return String.class;
    }

    @Override
    public String nullSafeGet(ResultSet rs, int position,
                               SharedSessionContractImplementor session,
                               Object owner) throws SQLException {
        String value = rs.getString(position);
        return value != null ? decrypt(value) : null;
    }

    @Override
    public void nullSafeSet(PreparedStatement st, String value, int index,
                            SharedSessionContractImplementor session) throws SQLException {
        if (value == null) {
            st.setNull(index, Types.VARCHAR);
        } else {
            st.setString(index, encrypt(value));
        }
    }

    @Override
    public boolean isMutable() {
        return false;
    }

    @Override
    public boolean equals(String x, String y) {
        return Objects.equals(x, y);
    }

    @Override
    public int hashCode(String x) {
        return x != null ? x.hashCode() : 0;
    }

    @Override
    public String deepCopy(String value) {
        return value;
    }

    @Override
    public Serializable disassemble(String value) {
        return value;
    }

    @Override
    public String assemble(Serializable cached, Object owner) {
        return (String) cached;
    }

    private String encrypt(String value) { /* AES encryption */ }
    private String decrypt(String value) { /* AES decryption */ }
}
```

### Usage

```java
@Entity
public class User {
    @Type(EncryptedStringType.class)
    private String ssn;
}
```

---

## Q187: How to map JSON columns in JPA/Hibernate?

### Approach 1: Using Vladmihalcea Hibernate Types Library (Recommended)

```xml
<dependency>
    <groupId>io.hypersistence</groupId>
    <artifactId>hypersistence-utils-hibernate-63</artifactId>
    <version>3.7.0</version>
</dependency>
```

```java
@Entity
@Table(name = "events")
public class Event {

    @Id
    @GeneratedValue
    private Long id;

    // Map to JSONB column (PostgreSQL)
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> properties;

    // Map a Java object to JSON
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private Address address;

    // List stored as JSON array
    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb")
    private List<String> tags;
}

// POJO for JSON mapping (no @Entity needed)
public class Address implements Serializable {
    private String street;
    private String city;
    private String zipCode;
    // getters/setters
}
```

### Approach 2: Using AttributeConverter

```java
@Converter
public class JsonMapConverter implements AttributeConverter<Map<String, Object>, String> {

    private static final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public String convertToDatabaseColumn(Map<String, Object> attribute) {
        try {
            return attribute == null ? null : objectMapper.writeValueAsString(attribute);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize JSON", e);
        }
    }

    @Override
    public Map<String, Object> convertToEntityAttribute(String dbData) {
        try {
            return dbData == null ? null :
                objectMapper.readValue(dbData, new TypeReference<>() {});
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize JSON", e);
        }
    }
}

@Entity
public class Event {
    @Convert(converter = JsonMapConverter.class)
    @Column(columnDefinition = "TEXT")
    private Map<String, Object> properties;
}
```

### Querying JSON Columns (PostgreSQL native)

```java
@Repository
public interface EventRepository extends JpaRepository<Event, Long> {

    @Query(value = "SELECT * FROM events WHERE properties->>'type' = :type",
           nativeQuery = true)
    List<Event> findByPropertyType(@Param("type") String type);

    @Query(value = "SELECT * FROM events WHERE properties @> CAST(:json AS jsonb)",
           nativeQuery = true)
    List<Event> findByJsonContaining(@Param("json") String json);
}
```

---

## Q188: What is @Converter and AttributeConverter?

`AttributeConverter` is a JPA interface that allows custom conversion between a Java type and its database representation.

### Basic Converter

```java
@Converter(autoApply = true)  // auto-apply to all fields of this type
public class MoneyConverter implements AttributeConverter<Money, Long> {

    @Override
    public Long convertToDatabaseColumn(Money money) {
        return money == null ? null : money.getAmountInCents();
    }

    @Override
    public Money convertToEntityAttribute(Long cents) {
        return cents == null ? null : Money.ofCents(cents);
    }
}
```

### Common Use Cases

**1. Enum with custom DB value:**

```java
public enum Priority {
    LOW(1), MEDIUM(2), HIGH(3), CRITICAL(4);

    private final int code;
    Priority(int code) { this.code = code; }
    public int getCode() { return code; }

    public static Priority fromCode(int code) {
        return Arrays.stream(values())
            .filter(p -> p.code == code)
            .findFirst()
            .orElseThrow();
    }
}

@Converter(autoApply = true)
public class PriorityConverter implements AttributeConverter<Priority, Integer> {
    @Override
    public Integer convertToDatabaseColumn(Priority priority) {
        return priority == null ? null : priority.getCode();
    }

    @Override
    public Priority convertToEntityAttribute(Integer code) {
        return code == null ? null : Priority.fromCode(code);
    }
}
```

**2. Encrypting sensitive data:**

```java
@Converter
public class EncryptionConverter implements AttributeConverter<String, String> {
    private final EncryptionService encryptionService = new EncryptionService();

    @Override
    public String convertToDatabaseColumn(String attribute) {
        return attribute == null ? null : encryptionService.encrypt(attribute);
    }

    @Override
    public String convertToEntityAttribute(String dbData) {
        return dbData == null ? null : encryptionService.decrypt(dbData);
    }
}

@Entity
public class Patient {
    @Convert(converter = EncryptionConverter.class)
    private String medicalRecordNumber;
}
```

**3. List to comma-separated string:**

```java
@Converter
public class StringListConverter implements AttributeConverter<List<String>, String> {

    @Override
    public String convertToDatabaseColumn(List<String> list) {
        return list == null ? null : String.join(",", list);
    }

    @Override
    public List<String> convertToEntityAttribute(String joined) {
        return joined == null ? Collections.emptyList() :
               Arrays.asList(joined.split(","));
    }
}
```

### Usage

```java
@Entity
public class Task {
    @Convert(converter = StringListConverter.class)
    @Column(name = "tags")
    private List<String> tags;

    // With autoApply=true, no @Convert needed
    private Priority priority;
}
```

### Limitations
- Converters don't work with `@Id` fields
- Cannot be used in JPQL comparisons directly (must compare DB representation)
- No access to other entity fields during conversion

---

## Q189: How to handle BLOB and CLOB in JPA?

### BLOB (Binary Large Object)

```java
@Entity
public class Document {

    @Id
    @GeneratedValue
    private Long id;

    private String filename;

    // Approach 1: byte array (loaded entirely into memory)
    @Lob
    @Column(name = "content", columnDefinition = "LONGBLOB")
    private byte[] content;

    // Approach 2: Blob interface (streaming, better for large files)
    @Lob
    private Blob fileBlob;

    private String contentType;
    private Long fileSize;
}
```

### CLOB (Character Large Object)

```java
@Entity
public class Article {

    @Id
    @GeneratedValue
    private Long id;

    private String title;

    // Approach 1: String (loaded entirely)
    @Lob
    @Column(columnDefinition = "TEXT")
    private String body;

    // Approach 2: Clob interface (streaming)
    @Lob
    private Clob bodyClob;
}
```

### Service Layer for BLOB Handling

```java
@Service
public class DocumentService {

    @PersistenceContext
    private EntityManager entityManager;

    @Autowired
    private DocumentRepository documentRepository;

    @Transactional
    public Document store(MultipartFile file) throws IOException {
        Document doc = new Document();
        doc.setFilename(file.getOriginalFilename());
        doc.setContentType(file.getContentType());
        doc.setFileSize(file.getSize());
        doc.setContent(file.getBytes());
        return documentRepository.save(doc);
    }

    // Using Blob for large files (streaming)
    @Transactional
    public Document storeStreaming(MultipartFile file) throws IOException {
        Session session = entityManager.unwrap(Session.class);
        Blob blob = session.getLobHelper()
            .createBlob(file.getInputStream(), file.getSize());

        Document doc = new Document();
        doc.setFilename(file.getOriginalFilename());
        doc.setFileBlob(blob);
        return documentRepository.save(doc);
    }

    @Transactional(readOnly = true)
    public void streamToResponse(Long docId, HttpServletResponse response)
            throws IOException, SQLException {
        Document doc = documentRepository.findById(docId).orElseThrow();
        response.setContentType(doc.getContentType());
        response.setHeader("Content-Disposition",
            "attachment; filename=\"" + doc.getFilename() + "\"");

        // Stream from Blob
        try (InputStream is = doc.getFileBlob().getBinaryStream();
             OutputStream os = response.getOutputStream()) {
            is.transferTo(os);
        }
    }
}
```

### Lazy Loading LOBs

```java
@Entity
public class Document {
    @Id
    @GeneratedValue
    private Long id;

    private String filename;

    @Lob
    @Basic(fetch = FetchType.LAZY)  // Lazy load the content
    private byte[] content;
}
```

> **Note:** Lazy loading of `@Lob` on basic types requires bytecode enhancement:

```xml
<plugin>
    <groupId>org.hibernate.orm.tooling</groupId>
    <artifactId>hibernate-enhance-maven-plugin</artifactId>
    <configuration>
        <enableLazyInitialization>true</enableLazyInitialization>
    </configuration>
</plugin>
```

---

## Q190: What is Spring Data REST? How to expose repositories as REST APIs?

**Spring Data REST** automatically exposes Spring Data repositories as hypermedia-driven RESTful resources (HAL+JSON).

### Dependency

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-rest</artifactId>
</dependency>
```

### Basic Usage — Just define entities and repositories:

```java
@Entity
public class Book {
    @Id
    @GeneratedValue
    private Long id;
    private String title;
    private String author;
    private BigDecimal price;
}

@RepositoryRestResource(path = "books", collectionResourceRel = "books")
public interface BookRepository extends JpaRepository<Book, Long> {

    List<Book> findByAuthor(@Param("author") String author);

    @RestResource(path = "expensive", rel = "expensive")
    List<Book> findByPriceGreaterThan(@Param("price") BigDecimal price);
}
```

This automatically creates:
- `GET /books` — list all (paginated)
- `GET /books/{id}` — single resource
- `POST /books` — create
- `PUT /books/{id}` — replace
- `PATCH /books/{id}` — partial update
- `DELETE /books/{id}` — delete
- `GET /books/search/findByAuthor?author=Tolkien` — custom query
- `GET /books/search/expensive?price=50` — custom query

### Configuration

```yaml
spring:
  data:
    rest:
      base-path: /api        # prefix all endpoints
      default-page-size: 20
      max-page-size: 100
      return-body-on-create: true
      return-body-on-update: true
```

### Customization

```java
// Hide a repository method from REST
@RepositoryRestResource
public interface UserRepository extends JpaRepository<User, Long> {

    @Override
    @RestResource(exported = false)  // Hide DELETE
    void deleteById(Long id);
}

// Projections (control what fields are exposed)
@Projection(name = "summary", types = Book.class)
public interface BookSummary {
    String getTitle();
    String getAuthor();
}
// Access: GET /books?projection=summary

// Event handlers
@RepositoryEventHandler
@Component
public class BookEventHandler {

    @HandleBeforeCreate
    public void handleBeforeCreate(Book book) {
        // validation, modification before save
    }

    @HandleAfterCreate
    public void handleAfterCreate(Book book) {
        // notifications, logging after save
    }
}
```

### Validators

```java
@Configuration
public class RestConfig implements RepositoryRestConfigurer {

    @Override
    public void configureValidatingRepositoryEventListener(
            ValidatingRepositoryEventListener listener) {
        listener.addValidator("beforeCreate", new BookValidator());
        listener.addValidator("beforeSave", new BookValidator());
    }
}
```

---

## Q191: What is the difference between Spring Data JPA and Spring Data JDBC?

| Aspect | Spring Data JPA | Spring Data JDBC |
|--------|----------------|-----------------|
| **ORM** | Full ORM (Hibernate) | No ORM, simple mapping |
| **Lazy Loading** | Yes | No (always eager) |
| **Caching** | L1, L2 cache | None |
| **Dirty Checking** | Automatic | No (explicit save) |
| **Associations** | Complex (OneToMany, ManyToMany, etc.) | Aggregate-based (DDD style) |
| **Identity Map** | Yes (persistence context) | No |
| **Complexity** | High | Low |
| **Performance** | Good with tuning | Predictable, transparent |
| **SQL Control** | Generated, sometimes surprising | More predictable |
| **Schema** | Can auto-generate | You manage schema |

### Spring Data JDBC Example

```java
// No @Entity, uses Spring's @Table
@Table("orders")
public class Order {

    @Id
    private Long id;
    private String customerName;
    private LocalDateTime orderDate;

    // Embedded one-to-many (aggregate root pattern)
    // Order "owns" its items — no separate repository for items
    @MappedCollection(idColumn = "order_id")
    private Set<OrderItem> items = new HashSet<>();
}

@Table("order_items")
public class OrderItem {
    private String product;
    private int quantity;
    private BigDecimal price;
}

public interface OrderRepository extends CrudRepository<Order, Long> {
    @Query("SELECT * FROM orders WHERE customer_name = :name")
    List<Order> findByCustomerName(@Param("name") String name);
}
```

### Key Philosophical Differences

**JPA:** Entity-centric, complex object graphs, implicit persistence
```java
// JPA - changes auto-detected
@Transactional
void updateName(Long id, String name) {
    User user = repo.findById(id).get();
    user.setName(name);  // auto-saved at transaction commit
}
```

**JDBC:** Aggregate-centric (DDD), explicit saves, no magic
```java
// JDBC - must explicitly save
void updateName(Long id, String name) {
    User user = repo.findById(id).get();
    user.setName(name);
    repo.save(user);  // explicit save required
}
```

### When to Use Which

- **Spring Data JPA:** Complex domains, legacy schemas, need lazy loading, complex relationships
- **Spring Data JDBC:** Simpler domains, want predictability, DDD aggregate pattern, microservices

---

## Q192: How to implement Event Sourcing with JPA?

**Event Sourcing** stores state changes as a sequence of events rather than storing current state directly.

### Event Store Entity

```java
@Entity
@Table(name = "event_store", indexes = {
    @Index(name = "idx_aggregate", columnList = "aggregateId,version")
})
public class StoredEvent {

    @Id
    @GeneratedValue
    private Long id;

    @Column(nullable = false)
    private String aggregateId;

    @Column(nullable = false)
    private String aggregateType;

    @Column(nullable = false)
    private String eventType;

    @Lob
    @Column(nullable = false)
    private String payload;  // JSON serialized event

    @Column(nullable = false)
    private int version;

    @Column(nullable = false)
    private Instant occurredAt;

    private String metadata;
}
```

### Domain Events

```java
public abstract class DomainEvent {
    private final Instant occurredAt = Instant.now();
    public Instant getOccurredAt() { return occurredAt; }
}

public class AccountCreatedEvent extends DomainEvent {
    private final String accountId;
    private final String ownerName;
    private final BigDecimal initialBalance;
    // constructor, getters
}

public class MoneyDepositedEvent extends DomainEvent {
    private final String accountId;
    private final BigDecimal amount;
    // constructor, getters
}

public class MoneyWithdrawnEvent extends DomainEvent {
    private final String accountId;
    private final BigDecimal amount;
    // constructor, getters
}
```

### Aggregate Root

```java
public class BankAccount {
    private String id;
    private String ownerName;
    private BigDecimal balance;
    private int version;
    private final List<DomainEvent> uncommittedEvents = new ArrayList<>();

    // Reconstruct from events
    public static BankAccount recreate(List<DomainEvent> history) {
        BankAccount account = new BankAccount();
        history.forEach(account::apply);
        account.uncommittedEvents.clear();
        return account;
    }

    // Command methods produce events
    public static BankAccount create(String id, String owner, BigDecimal initial) {
        BankAccount account = new BankAccount();
        account.raise(new AccountCreatedEvent(id, owner, initial));
        return account;
    }

    public void deposit(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0)
            throw new IllegalArgumentException("Amount must be positive");
        raise(new MoneyDepositedEvent(id, amount));
    }

    public void withdraw(BigDecimal amount) {
        if (amount.compareTo(balance) > 0)
            throw new IllegalStateException("Insufficient funds");
        raise(new MoneyWithdrawnEvent(id, amount));
    }

    private void raise(DomainEvent event) {
        apply(event);
        uncommittedEvents.add(event);
    }

    private void apply(DomainEvent event) {
        if (event instanceof AccountCreatedEvent e) {
            this.id = e.getAccountId();
            this.ownerName = e.getOwnerName();
            this.balance = e.getInitialBalance();
        } else if (event instanceof MoneyDepositedEvent e) {
            this.balance = this.balance.add(e.getAmount());
        } else if (event instanceof MoneyWithdrawnEvent e) {
            this.balance = this.balance.subtract(e.getAmount());
        }
        this.version++;
    }

    public List<DomainEvent> getUncommittedEvents() {
        return Collections.unmodifiableList(uncommittedEvents);
    }
}
```

### Event Store Repository and Service

```java
@Repository
public interface EventStoreRepository extends JpaRepository<StoredEvent, Long> {

    List<StoredEvent> findByAggregateIdOrderByVersionAsc(String aggregateId);

    @Query("SELECT MAX(e.version) FROM StoredEvent e WHERE e.aggregateId = :id")
    Optional<Integer> findMaxVersion(@Param("id") String aggregateId);
}

@Service
@Transactional
public class EventStoreService {

    @Autowired
    private EventStoreRepository repository;

    @Autowired
    private ObjectMapper objectMapper;

    public void saveEvents(String aggregateId, String aggregateType,
                           List<DomainEvent> events, int expectedVersion) {
        // Optimistic concurrency check
        int currentVersion = repository.findMaxVersion(aggregateId).orElse(0);
        if (currentVersion != expectedVersion) {
            throw new OptimisticLockException("Concurrent modification detected");
        }

        int version = expectedVersion;
        for (DomainEvent event : events) {
            version++;
            StoredEvent stored = new StoredEvent();
            stored.setAggregateId(aggregateId);
            stored.setAggregateType(aggregateType);
            stored.setEventType(event.getClass().getSimpleName());
            stored.setPayload(serialize(event));
            stored.setVersion(version);
            stored.setOccurredAt(event.getOccurredAt());
            repository.save(stored);
        }
    }

    public List<DomainEvent> loadEvents(String aggregateId) {
        return repository.findByAggregateIdOrderByVersionAsc(aggregateId)
            .stream()
            .map(stored -> deserialize(stored.getPayload(), stored.getEventType()))
            .toList();
    }

    private String serialize(DomainEvent event) { /* JSON serialize */ }
    private DomainEvent deserialize(String json, String type) { /* JSON deserialize */ }
}
```

---

## Q193: What is Reactive Spring Data (R2DBC)? How is it different from JPA?

**R2DBC** (Reactive Relational Database Connectivity) provides non-blocking database access for reactive applications.

### Key Differences

| Aspect | JPA/JDBC | R2DBC |
|--------|----------|-------|
| **I/O Model** | Blocking | Non-blocking (reactive) |
| **Thread Model** | Thread-per-request | Event loop (few threads) |
| **API** | `List<T>`, `Optional<T>` | `Flux<T>`, `Mono<T>` |
| **ORM** | Full ORM (Hibernate) | No ORM, simple mapping |
| **Lazy Loading** | Yes | No |
| **Transactions** | `@Transactional` (blocking) | `@Transactional` (reactive) |
| **Relationships** | Automatic | Manual |
| **Maturity** | Very mature | Relatively new |

### Setup

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-r2dbc</artifactId>
</dependency>
<dependency>
    <groupId>org.postgresql</groupId>
    <artifactId>r2dbc-postgresql</artifactId>
</dependency>
```

```yaml
spring:
  r2dbc:
    url: r2dbc:postgresql://localhost:5432/mydb
    username: user
    password: pass
```

### Entity and Repository

```java
@Table("products")
public class Product {
    @Id
    private Long id;
    private String name;
    private BigDecimal price;
    private LocalDateTime createdAt;
}

public interface ProductRepository extends ReactiveCrudRepository<Product, Long> {

    Flux<Product> findByNameContaining(String name);

    @Query("SELECT * FROM products WHERE price > :minPrice ORDER BY price")
    Flux<Product> findExpensive(@Param("minPrice") BigDecimal minPrice);

    Mono<Long> countByPriceGreaterThan(BigDecimal price);
}
```

### Reactive Controller

```java
@RestController
@RequestMapping("/products")
public class ProductController {

    @Autowired
    private ProductRepository repository;

    @GetMapping
    public Flux<Product> getAll() {
        return repository.findAll();
    }

    @GetMapping("/{id}")
    public Mono<ResponseEntity<Product>> getById(@PathVariable Long id) {
        return repository.findById(id)
            .map(ResponseEntity::ok)
            .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @PostMapping
    public Mono<Product> create(@RequestBody Product product) {
        return repository.save(product);
    }

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<Product> stream() {
        return repository.findAll().delayElements(Duration.ofSeconds(1));
    }
}
```

### Reactive Transactions

```java
@Service
public class OrderService {

    @Autowired
    private TransactionalOperator transactionalOperator;

    // Declarative
    @Transactional
    public Mono<Order> placeOrder(Order order) {
        return orderRepository.save(order)
            .flatMap(saved -> inventoryRepository.decreaseStock(saved.getProductId()))
            .thenReturn(order);
    }

    // Programmatic
    public Mono<Order> placeOrderProgrammatic(Order order) {
        return transactionalOperator.transactional(
            orderRepository.save(order)
                .flatMap(saved -> inventoryRepository.decreaseStock(saved.getProductId()))
        );
    }
}
```

### When to Use R2DBC vs JPA

- **Use JPA:** Complex domain models, need ORM features, existing blocking codebase
- **Use R2DBC:** High-concurrency services, streaming data, reactive microservices, need maximum throughput with minimal threads

---

## Q194: How to handle database connection failover and read replicas?

### Read/Write Splitting with AbstractRoutingDataSource

```java
public enum DataSourceType {
    PRIMARY, REPLICA
}

public class RoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return DataSourceContext.getDataSourceType();
    }
}

public class DataSourceContext {
    private static final ThreadLocal<DataSourceType> CONTEXT =
        ThreadLocal.withInitial(() -> DataSourceType.PRIMARY);

    public static void setDataSourceType(DataSourceType type) {
        CONTEXT.set(type);
    }

    public static DataSourceType getDataSourceType() {
        return CONTEXT.get();
    }

    public static void clear() {
        CONTEXT.remove();
    }
}
```

### Configuration

```java
@Configuration
public class DataSourceConfig {

    @Bean
    public DataSource routingDataSource() {
        RoutingDataSource routing = new RoutingDataSource();

        DataSource primary = DataSourceBuilder.create()
            .url("jdbc:postgresql://primary-host:5432/mydb")
            .username("user").password("pass").build();

        DataSource replica = DataSourceBuilder.create()
            .url("jdbc:postgresql://replica-host:5432/mydb")
            .username("user").password("pass").build();

        Map<Object, Object> dataSources = new HashMap<>();
        dataSources.put(DataSourceType.PRIMARY, primary);
        dataSources.put(DataSourceType.REPLICA, replica);

        routing.setTargetDataSources(dataSources);
        routing.setDefaultTargetDataSource(primary);

        return routing;
    }

    @Bean
    public DataSource dataSource() {
        return new LazyConnectionDataSourceProxy(routingDataSource());
    }
}
```

### AOP-Based Routing

```java
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
public @interface ReadOnlyConnection {}

@Aspect
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class ReadOnlyDataSourceAspect {

    @Around("@annotation(readOnly) || @within(readOnly)")
    public Object route(ProceedingJoinPoint joinPoint,
                        ReadOnlyConnection readOnly) throws Throwable {
        try {
            DataSourceContext.setDataSourceType(DataSourceType.REPLICA);
            return joinPoint.proceed();
        } finally {
            DataSourceContext.clear();
        }
    }
}

// Usage
@Service
public class ProductService {

    @ReadOnlyConnection
    @Transactional(readOnly = true)
    public List<Product> findAll() {
        return productRepository.findAll(); // goes to replica
    }

    @Transactional
    public Product save(Product product) {
        return productRepository.save(product); // goes to primary
    }
}
```

### Automatic Routing Based on @Transactional(readOnly)

```java
@Aspect
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TransactionReadOnlyAspect {

    @Around("@annotation(transactional)")
    public Object route(ProceedingJoinPoint pjp,
                        Transactional transactional) throws Throwable {
        try {
            if (transactional.readOnly()) {
                DataSourceContext.setDataSourceType(DataSourceType.REPLICA);
            } else {
                DataSourceContext.setDataSourceType(DataSourceType.PRIMARY);
            }
            return pjp.proceed();
        } finally {
            DataSourceContext.clear();
        }
    }
}
```

### Connection Failover with HikariCP

```yaml
spring:
  datasource:
    url: jdbc:postgresql://primary:5432,failover:5432/mydb?targetServerType=primary
    hikari:
      connection-timeout: 5000
      validation-timeout: 3000
      max-lifetime: 600000
      keepalive-time: 30000
      connection-test-query: SELECT 1
```

### Multiple Replicas with Load Balancing

```java
@Bean
public DataSource replicaDataSource() {
    // Round-robin across replicas
    List<DataSource> replicas = List.of(
        createDataSource("jdbc:postgresql://replica1:5432/mydb"),
        createDataSource("jdbc:postgresql://replica2:5432/mydb"),
        createDataSource("jdbc:postgresql://replica3:5432/mydb")
    );

    AtomicInteger counter = new AtomicInteger(0);

    return new AbstractDataSource() {
        @Override
        public Connection getConnection() throws SQLException {
            int index = Math.abs(counter.getAndIncrement() % replicas.size());
            return replicas.get(index).getConnection();
        }
        @Override
        public Connection getConnection(String u, String p) throws SQLException {
            return getConnection();
        }
    };
}
```

---

## Q195: What is QueryDSL and how to use it with Spring Data JPA?

**QueryDSL** is a framework for building type-safe queries in Java, generating query classes (Q-classes) from your entities at compile time.

### Setup

```xml
<dependency>
    <groupId>com.querydsl</groupId>
    <artifactId>querydsl-jpa</artifactId>
    <classifier>jakarta</classifier>
</dependency>
<dependency>
    <groupId>com.querydsl</groupId>
    <artifactId>querydsl-apt</artifactId>
    <classifier>jakarta</classifier>
    <scope>provided</scope>
</dependency>

<!-- Maven APT plugin to generate Q-classes -->
<plugin>
    <groupId>com.mysema.maven</groupId>
    <artifactId>apt-maven-plugin</artifactId>
    <version>1.1.3</version>
    <executions>
        <execution>
            <goals><goal>process</goal></goals>
            <configuration>
                <outputDirectory>target/generated-sources/java</outputDirectory>
                <processor>com.querydsl.apt.jpa.JPAAnnotationProcessor</processor>
            </configuration>
        </execution>
    </executions>
</plugin>
```

### Entity

```java
@Entity
public class Product {
    @Id
    @GeneratedValue
    private Long id;
    private String name;
    private BigDecimal price;
    private String category;
    private boolean active;
    private LocalDate createdAt;

    @ManyToOne
    private Brand brand;
}
```

This generates `QProduct` at compile time.

### Repository with QueryDSL Support

```java
public interface ProductRepository extends JpaRepository<Product, Long>,
                                           QuerydslPredicateExecutor<Product> {
}
```

### Basic Queries

```java
@Service
public class ProductService {

    @Autowired
    private ProductRepository productRepository;

    public List<Product> findActiveExpensive(BigDecimal minPrice) {
        QProduct product = QProduct.product;

        BooleanExpression predicate = product.active.isTrue()
            .and(product.price.gt(minPrice));

        return (List<Product>) productRepository.findAll(predicate);
    }

    public Page<Product> search(String name, String category,
                                 BigDecimal minPrice, BigDecimal maxPrice,
                                 Pageable pageable) {
        QProduct product = QProduct.product;

        BooleanBuilder builder = new BooleanBuilder();

        if (name != null) {
            builder.and(product.name.containsIgnoreCase(name));
        }
        if (category != null) {
            builder.and(product.category.eq(category));
        }
        if (minPrice != null) {
            builder.and(product.price.goe(minPrice));
        }
        if (maxPrice != null) {
            builder.and(product.price.loe(maxPrice));
        }

        return productRepository.findAll(builder, pageable);
    }
}
```

### Advanced Queries with JPAQueryFactory

```java
@Repository
public class ProductQueryRepository {

    @PersistenceContext
    private EntityManager entityManager;

    private JPAQueryFactory queryFactory() {
        return new JPAQueryFactory(entityManager);
    }

    // Join query
    public List<Product> findByBrandName(String brandName) {
        QProduct product = QProduct.product;
        QBrand brand = QBrand.brand;

        return queryFactory()
            .selectFrom(product)
            .join(product.brand, brand)
            .where(brand.name.eq(brandName))
            .orderBy(product.price.desc())
            .fetch();
    }

    // Projection (DTO)
    public List<ProductDTO> findProductSummaries() {
        QProduct product = QProduct.product;

        return queryFactory()
            .select(Projections.constructor(ProductDTO.class,
                product.id,
                product.name,
                product.price))
            .from(product)
            .where(product.active.isTrue())
            .fetch();
    }

    // Subquery
    public List<Product> findCheaperThanAverage() {
        QProduct product = QProduct.product;
        QProduct sub = new QProduct("sub");

        return queryFactory()
            .selectFrom(product)
            .where(product.price.lt(
                JPAExpressions.select(sub.price.avg()).from(sub)
            ))
            .fetch();
    }

    // Aggregation
    public Map<String, BigDecimal> avgPriceByCategory() {
        QProduct product = QProduct.product;

        return queryFactory()
            .select(product.category, product.price.avg())
            .from(product)
            .groupBy(product.category)
            .fetch()
            .stream()
            .collect(Collectors.toMap(
                tuple -> tuple.get(product.category),
                tuple -> BigDecimal.valueOf(tuple.get(product.price.avg()))
            ));
    }

    // Update
    @Transactional
    public long deactivateOld(LocalDate before) {
        QProduct product = QProduct.product;

        return queryFactory()
            .update(product)
            .set(product.active, false)
            .where(product.createdAt.before(before))
            .execute();
    }
}
```

### QueryDSL Web Support (auto-bind request params to predicates)

```java
@Configuration
public class QueryDslConfig {
    @Bean
    public QuerydslBinderCustomizer<QProduct> productBinderCustomizer() {
        return (bindings, root) -> {
            bindings.bind(root.name).first(StringExpression::containsIgnoreCase);
            bindings.bind(root.price).all((path, values) -> {
                Iterator<? extends BigDecimal> it = values.iterator();
                return Optional.of(path.between(it.next(), it.next()));
            });
        };
    }
}

@RestController
public class ProductController {

    @GetMapping("/products")
    public Page<Product> search(
            @QuerydslPredicate(root = Product.class) Predicate predicate,
            Pageable pageable) {
        return productRepository.findAll(predicate, pageable);
    }
    // GET /products?name=laptop&category=electronics&price=100&price=500
}
```

### QueryDSL vs Other Approaches

| Approach | Type-Safe | Dynamic | Readable | Setup |
|----------|-----------|---------|----------|-------|
| JPQL | No | Limited | Medium | None |
| Criteria API | Yes | Yes | Low | None |
| QueryDSL | Yes | Yes | High | Code generation |
| Specifications | Partial | Yes | Medium | None |

---
