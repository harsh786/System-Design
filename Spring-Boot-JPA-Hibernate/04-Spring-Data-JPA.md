# Spring Data JPA - Interview Questions (Q66-Q90)

---

## Q66: What is Spring Data JPA? How does it simplify data access?

Spring Data JPA is a part of the Spring Data project that makes it easy to implement JPA-based repositories. It reduces boilerplate code by providing repository abstractions that automatically generate implementations at runtime.

### How it simplifies data access:

1. **No implementation needed** — Just define an interface, Spring generates the implementation
2. **Derived queries** — Method names are parsed into queries automatically
3. **Built-in CRUD** — Common operations are provided out of the box
4. **Pagination & Sorting** — Built-in support without manual SQL
5. **Custom queries** — Easy `@Query` annotation for complex cases

```java
// Traditional JPA DAO - lots of boilerplate
@Repository
public class EmployeeDaoImpl implements EmployeeDao {
    @PersistenceContext
    private EntityManager em;

    public Employee findById(Long id) {
        return em.find(Employee.class, id);
    }

    public List<Employee> findAll() {
        return em.createQuery("SELECT e FROM Employee e", Employee.class).getResultList();
    }

    public Employee save(Employee employee) {
        if (employee.getId() == null) {
            em.persist(employee);
            return employee;
        } else {
            return em.merge(employee);
        }
    }

    public void delete(Employee employee) {
        em.remove(em.contains(employee) ? employee : em.merge(employee));
    }
}

// Spring Data JPA - just an interface!
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    // All CRUD methods are automatically available
    // Plus you can add custom query methods
    List<Employee> findByDepartment(String department);
}
```

### Dependency:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
```

---

## Q67: What is the Repository pattern in Spring Data JPA?

The Repository pattern is a design pattern that mediates between the domain and data mapping layers. In Spring Data JPA, repositories are interfaces that Spring implements at runtime using proxies.

### Key Concepts:

- **Domain-Driven Design origin** — Repository encapsulates storage/retrieval logic
- **Interface-based programming** — You declare, Spring implements
- **Proxy-based** — Spring uses `SimpleJpaRepository` as the default implementation

```java
// Marker interface - no methods
public interface EmployeeRepository extends Repository<Employee, Long> {
    // Only methods you declare are available
    Optional<Employee> findById(Long id);
    Employee save(Employee employee);
}

// Or extend CrudRepository for full CRUD
public interface EmployeeRepository extends CrudRepository<Employee, Long> {
    // All CRUD methods inherited
}
```

### How Spring creates the implementation:

1. Spring scans for interfaces extending `Repository` (or sub-interfaces)
2. Creates a JDK dynamic proxy for each interface
3. The proxy delegates to `SimpleJpaRepository` (default implementation)
4. Custom query methods are resolved via method name parsing or `@Query`

```java
// You can also use @RepositoryDefinition instead of extending Repository
@RepositoryDefinition(domainClass = Employee.class, idClass = Long.class)
public interface EmployeeRepository {
    Optional<Employee> findById(Long id);
    Employee save(Employee employee);
}
```

---

## Q68: Explain the repository hierarchy (Repository, CrudRepository, PagingAndSortingRepository, JpaRepository)

```
Repository<T, ID>                         (Marker interface - no methods)
    │
    └── CrudRepository<T, ID>             (Basic CRUD operations)
            │
            └── ListCrudRepository<T, ID> (Returns List instead of Iterable)
            │
            └── PagingAndSortingRepository<T, ID>  (Pagination + Sorting)
                    │
                    └── JpaRepository<T, ID>       (JPA-specific methods: flush, batch)
```

### Repository (Marker Interface)

```java
public interface Repository<T, ID> {
    // No methods - just a marker
    // Use when you want to selectively expose methods
}
```

### CrudRepository

```java
public interface CrudRepository<T, ID> extends Repository<T, ID> {
    <S extends T> S save(S entity);
    <S extends T> Iterable<S> saveAll(Iterable<S> entities);
    Optional<T> findById(ID id);
    boolean existsById(ID id);
    Iterable<T> findAll();
    Iterable<T> findAllById(Iterable<ID> ids);
    long count();
    void deleteById(ID id);
    void delete(T entity);
    void deleteAllById(Iterable<? extends ID> ids);
    void deleteAll(Iterable<? extends T> entities);
    void deleteAll();
}
```

### PagingAndSortingRepository

```java
public interface PagingAndSortingRepository<T, ID> extends Repository<T, ID> {
    Iterable<T> findAll(Sort sort);
    Page<T> findAll(Pageable pageable);
}
```

### JpaRepository

```java
public interface JpaRepository<T, ID> extends ListCrudRepository<T, ID>,
        ListPagingAndSortingRepository<T, ID>, QueryByExampleExecutor<T> {

    void flush();
    <S extends T> S saveAndFlush(S entity);
    <S extends T> List<S> saveAllAndFlush(Iterable<S> entities);
    void deleteInBatch(Iterable<T> entities);
    void deleteAllInBatch();
    void deleteAllByIdInBatch(Iterable<ID> ids);
    T getReferenceById(ID id);  // Returns a proxy (lazy)
    // Also inherits QueryByExampleExecutor methods
}
```

### When to use which:

| Interface | Use Case |
|-----------|----------|
| `Repository` | Expose only selected methods |
| `CrudRepository` | Basic CRUD without pagination |
| `PagingAndSortingRepository` | Need pagination/sorting |
| `JpaRepository` | Full JPA features (flush, batch delete, Query by Example) |

```java
// Most common usage
public interface ProductRepository extends JpaRepository<Product, Long> {
    List<Product> findByCategory(String category);
}
```

---

## Q69: What are derived/query methods? How does method name parsing work?

Derived query methods are repository methods where Spring Data JPA parses the method name and automatically generates the JPQL query.

### Method Name Structure:

```
find|read|get|query|search|stream + By + PropertyExpression + Keyword + ...
```

### Examples:

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // SELECT e FROM Employee e WHERE e.name = ?1
    List<Employee> findByName(String name);

    // SELECT e FROM Employee e WHERE e.name = ?1 AND e.department = ?2
    List<Employee> findByNameAndDepartment(String name, String department);

    // SELECT e FROM Employee e WHERE e.salary > ?1
    List<Employee> findBySalaryGreaterThan(Double salary);

    // SELECT e FROM Employee e WHERE e.name LIKE ?1
    List<Employee> findByNameContaining(String name);

    // SELECT e FROM Employee e WHERE e.active = true
    List<Employee> findByActiveTrue();

    // SELECT e FROM Employee e WHERE e.department IS NULL
    List<Employee> findByDepartmentIsNull();

    // With ordering
    List<Employee> findByDepartmentOrderBySalaryDesc(String dept);

    // Limiting results
    List<Employee> findTop5BySalaryGreaterThan(Double salary);
    Employee findFirstByOrderBySalaryDesc();

    // Count queries
    long countByDepartment(String department);

    // Exists queries
    boolean existsByEmail(String email);

    // Delete queries
    void deleteByEmail(String email);
    long deleteByDepartment(String department); // returns count

    // Distinct
    List<Employee> findDistinctByDepartment(String department);
}
```

### Nested Property Traversal:

```java
// Entity
@Entity
public class Employee {
    @ManyToOne
    private Department department; // Department has a 'name' field
    
    @Embedded
    private Address address; // Address has 'city' field
}

// Traverses: employee.department.name
List<Employee> findByDepartmentName(String deptName);

// Traverses: employee.address.city
List<Employee> findByAddressCity(String city);

// Use underscore to clarify ambiguity
// If Employee has both 'departmentName' and department.name
List<Employee> findByDepartment_Name(String name); // Forces traversal
```

---

## Q70: What keywords are supported in derived query methods?

### Comparison Keywords:

| Keyword | Sample | JPQL Equivalent |
|---------|--------|-----------------|
| `Is`, `Equals` | `findByNameIs(String)` | `WHERE x.name = ?1` |
| `Not` | `findByNameNot(String)` | `WHERE x.name <> ?1` |
| `IsNull`, `Null` | `findByNameIsNull()` | `WHERE x.name IS NULL` |
| `IsNotNull`, `NotNull` | `findByNameIsNotNull()` | `WHERE x.name IS NOT NULL` |
| `IsTrue`, `True` | `findByActiveTrue()` | `WHERE x.active = true` |
| `IsFalse`, `False` | `findByActiveFalse()` | `WHERE x.active = false` |

### Range Keywords:

| Keyword | Sample | JPQL Equivalent |
|---------|--------|-----------------|
| `LessThan` | `findBySalaryLessThan(Double)` | `WHERE x.salary < ?1` |
| `LessThanEqual` | `findBySalaryLessThanEqual(Double)` | `WHERE x.salary <= ?1` |
| `GreaterThan` | `findBySalaryGreaterThan(Double)` | `WHERE x.salary > ?1` |
| `GreaterThanEqual` | `findBySalaryGreaterThanEqual(Double)` | `WHERE x.salary >= ?1` |
| `Between` | `findBySalaryBetween(Double, Double)` | `WHERE x.salary BETWEEN ?1 AND ?2` |
| `Before` | `findByDateBefore(Date)` | `WHERE x.date < ?1` |
| `After` | `findByDateAfter(Date)` | `WHERE x.date > ?1` |

### String Keywords:

| Keyword | Sample | JPQL Equivalent |
|---------|--------|-----------------|
| `Like` | `findByNameLike(String)` | `WHERE x.name LIKE ?1` |
| `NotLike` | `findByNameNotLike(String)` | `WHERE x.name NOT LIKE ?1` |
| `StartingWith` | `findByNameStartingWith(String)` | `WHERE x.name LIKE ?1 + '%'` |
| `EndingWith` | `findByNameEndingWith(String)` | `WHERE x.name LIKE '%' + ?1` |
| `Containing` | `findByNameContaining(String)` | `WHERE x.name LIKE '%' + ?1 + '%'` |

### Collection Keywords:

| Keyword | Sample | JPQL Equivalent |
|---------|--------|-----------------|
| `In` | `findByNameIn(Collection)` | `WHERE x.name IN ?1` |
| `NotIn` | `findByNameNotIn(Collection)` | `WHERE x.name NOT IN ?1` |

### Logical Keywords:

| Keyword | Sample | JPQL Equivalent |
|---------|--------|-----------------|
| `And` | `findByNameAndAge(String, int)` | `WHERE x.name = ?1 AND x.age = ?2` |
| `Or` | `findByNameOrAge(String, int)` | `WHERE x.name = ?1 OR x.age = ?2` |

### Result Limiting:

| Keyword | Sample |
|---------|--------|
| `First`, `Top` | `findFirst3ByOrderBySalaryDesc()` |
| `Distinct` | `findDistinctByDepartment(String)` |

### Ordering:

| Keyword | Sample |
|---------|--------|
| `OrderBy...Asc` | `findByDeptOrderByNameAsc(String)` |
| `OrderBy...Desc` | `findByDeptOrderBySalaryDesc(String)` |

---

## Q71: What is @Query annotation? How to write custom queries?

`@Query` allows you to define custom JPQL or native SQL queries directly on repository methods, useful when derived queries become too complex.

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // JPQL query (default)
    @Query("SELECT e FROM Employee e WHERE e.salary > :salary AND e.department = :dept")
    List<Employee> findHighEarners(@Param("dept") String department,
                                   @Param("salary") Double salary);

    // Positional parameters
    @Query("SELECT e FROM Employee e WHERE e.name = ?1 AND e.department = ?2")
    List<Employee> findByNameAndDept(String name, String department);

    // Native SQL query
    @Query(value = "SELECT * FROM employees WHERE department = ?1", nativeQuery = true)
    List<Employee> findByDeptNative(String department);

    // Using LIKE
    @Query("SELECT e FROM Employee e WHERE e.name LIKE %:keyword%")
    List<Employee> searchByName(@Param("keyword") String keyword);

    // Returning DTOs via constructor expression
    @Query("SELECT new com.example.dto.EmployeeDTO(e.name, e.salary) FROM Employee e WHERE e.department = :dept")
    List<EmployeeDTO> findEmployeeDTOs(@Param("dept") String department);

    // COUNT query
    @Query("SELECT COUNT(e) FROM Employee e WHERE e.department = :dept")
    long countByDept(@Param("dept") String department);

    // IN clause
    @Query("SELECT e FROM Employee e WHERE e.department IN :departments")
    List<Employee> findByDepartments(@Param("departments") List<String> departments);

    // JOIN query
    @Query("SELECT e FROM Employee e JOIN e.projects p WHERE p.name = :projectName")
    List<Employee> findByProjectName(@Param("projectName") String projectName);

    // Pagination with @Query
    @Query("SELECT e FROM Employee e WHERE e.department = :dept")
    Page<Employee> findByDepartment(@Param("dept") String dept, Pageable pageable);

    // SpEL expressions (entity name)
    @Query("SELECT e FROM #{#entityName} e WHERE e.active = true")
    List<Employee> findAllActive();
}
```

---

## Q72: What is the difference between JPQL and native queries in @Query?

| Aspect | JPQL | Native Query |
|--------|------|--------------|
| Syntax | Entity/class names | Table/column names |
| Portability | Database-independent | Database-specific |
| Feature access | JPA features only | Full SQL (window functions, CTEs, etc.) |
| Mapping | Automatic to entities | Needs `@SqlResultSetMapping` or interface projection |
| Pagination | Automatic | Requires `countQuery` |

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    // JPQL - uses entity names and fields
    @Query("SELECT o FROM Order o WHERE o.customer.name = :name")
    List<Order> findByCustomerJPQL(@Param("name") String customerName);

    // Native - uses table and column names
    @Query(value = "SELECT o.* FROM orders o JOIN customers c ON o.customer_id = c.id WHERE c.name = :name",
           nativeQuery = true)
    List<Order> findByCustomerNative(@Param("name") String customerName);

    // Native with pagination - MUST provide countQuery
    @Query(value = "SELECT * FROM orders WHERE status = :status",
           countQuery = "SELECT COUNT(*) FROM orders WHERE status = :status",
           nativeQuery = true)
    Page<Order> findByStatusNative(@Param("status") String status, Pageable pageable);

    // Native with complex SQL (window functions not available in JPQL)
    @Query(value = """
        SELECT *, RANK() OVER (PARTITION BY department ORDER BY salary DESC) as salary_rank
        FROM employees
        WHERE department = :dept
        """, nativeQuery = true)
    List<Object[]> findWithSalaryRank(@Param("dept") String department);

    // Native with projection mapping
    @Query(value = "SELECT name, SUM(amount) as total FROM orders GROUP BY name",
           nativeQuery = true)
    List<OrderSummaryProjection> getOrderSummary();
}

interface OrderSummaryProjection {
    String getName();
    Double getTotal();
}
```

### When to use Native Queries:

- Database-specific features (window functions, CTEs, `LATERAL JOIN`)
- Performance-critical queries that need specific SQL optimization
- Legacy database schemas with non-standard naming
- Calling database functions not supported in JPQL

---

## Q73: How to use @Modifying annotation for update/delete queries?

`@Modifying` marks a query method as a modifying query (INSERT/UPDATE/DELETE) rather than a selecting one. Required for any `@Query` that changes data.

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // UPDATE query
    @Modifying
    @Query("UPDATE Employee e SET e.salary = :salary WHERE e.department = :dept")
    int updateSalaryByDepartment(@Param("dept") String department,
                                  @Param("salary") Double salary);

    // DELETE query
    @Modifying
    @Query("DELETE FROM Employee e WHERE e.active = false")
    int deleteInactiveEmployees();

    // Bulk update
    @Modifying
    @Query("UPDATE Employee e SET e.department = :newDept WHERE e.id IN :ids")
    int bulkUpdateDepartment(@Param("ids") List<Long> ids,
                             @Param("newDept") String newDepartment);

    // Native modifying query
    @Modifying
    @Query(value = "UPDATE employees SET status = 'ARCHIVED' WHERE last_login < :date",
           nativeQuery = true)
    int archiveOldAccounts(@Param("date") LocalDate date);

    // clearAutomatically - clears persistence context after execution
    @Modifying(clearAutomatically = true)
    @Query("UPDATE Employee e SET e.salary = e.salary * 1.1 WHERE e.department = :dept")
    int giveRaise(@Param("dept") String department);

    // flushAutomatically - flushes before executing
    @Modifying(flushAutomatically = true)
    @Query("DELETE FROM Employee e WHERE e.id = :id")
    void deleteEmployee(@Param("id") Long id);
}
```

### Important Notes:

```java
@Service
@Transactional // @Modifying queries MUST run within a transaction
public class EmployeeService {

    @Autowired
    private EmployeeRepository repo;

    public void deactivateDepartment(String dept) {
        // This bypasses JPA lifecycle (no @PreUpdate callbacks)
        int count = repo.updateSalaryByDepartment(dept, 0.0);

        // WARNING: Persistence context is now stale!
        // Entities loaded before this update still have old values.
        // Use clearAutomatically = true, or manually:
        // entityManager.clear();
    }
}
```

**Key points:**
- Return type can be `void`, `int`, or `Integer` (affected row count)
- Bypasses entity lifecycle callbacks (`@PreUpdate`, `@PreRemove`)
- Does NOT update first-level cache — use `clearAutomatically = true`
- Must be used within `@Transactional`

---

## Q74: What is @Param annotation in Spring Data JPA?

`@Param` binds method parameters to named parameters in `@Query` annotations.

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // Named parameters with @Param
    @Query("SELECT e FROM Employee e WHERE e.name = :name AND e.department = :dept")
    List<Employee> findByNameAndDept(@Param("name") String employeeName,
                                     @Param("dept") String department);

    // Without @Param - uses positional parameters (?1, ?2)
    @Query("SELECT e FROM Employee e WHERE e.name = ?1 AND e.department = ?2")
    List<Employee> findByNameAndDept2(String name, String department);

    // @Param with IN clause
    @Query("SELECT e FROM Employee e WHERE e.status IN :statuses")
    List<Employee> findByStatuses(@Param("statuses") List<String> statuses);

    // SpEL with @Param
    @Query("SELECT e FROM Employee e WHERE e.name = :#{#filter.name} AND e.department = :#{#filter.dept}")
    List<Employee> findByFilter(@Param("filter") EmployeeFilter filter);
}
```

> **Note:** With Java 8+ and `-parameters` compiler flag (default in Spring Boot), `@Param` is optional if parameter names match query parameter names. However, it's best practice to include it for clarity.

---

## Q75: Explain Pagination and Sorting in Spring Data JPA (Pageable, Sort, Page, Slice)

### Pageable - Request Object:

```java
// Creating Pageable
Pageable pageable = PageRequest.of(0, 10); // page 0, size 10
Pageable pageable = PageRequest.of(0, 10, Sort.by("salary").descending());
Pageable pageable = PageRequest.of(0, 10,
    Sort.by(Sort.Direction.DESC, "salary")
         .and(Sort.by(Sort.Direction.ASC, "name")));
```

### Sort:

```java
// Simple sort
Sort sort = Sort.by("name");
Sort sort = Sort.by(Sort.Direction.DESC, "salary");

// Multiple sorts
Sort sort = Sort.by("department").ascending()
               .and(Sort.by("salary").descending());

// Type-safe sort using method references (JPA metamodel)
Sort sort = Sort.by(Sort.Order.asc("name"), Sort.Order.desc("salary"));

// Unsorted
Sort sort = Sort.unsorted();
```

### Repository Methods:

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // Returns Page (with total count)
    Page<Employee> findByDepartment(String department, Pageable pageable);

    // Returns Slice (no total count - better performance)
    Slice<Employee> findByStatus(String status, Pageable pageable);

    // Returns List (sorted, no pagination metadata)
    List<Employee> findByDepartment(String department, Sort sort);

    // Custom query with pagination
    @Query("SELECT e FROM Employee e WHERE e.salary > :min")
    Page<Employee> findHighEarners(@Param("min") Double minSalary, Pageable pageable);
}
```

### Service/Controller Usage:

```java
@RestController
public class EmployeeController {

    @Autowired
    private EmployeeRepository repo;

    @GetMapping("/employees")
    public Page<Employee> getEmployees(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "name") String sortBy,
            @RequestParam(defaultValue = "asc") String direction) {

        Sort sort = direction.equalsIgnoreCase("desc")
            ? Sort.by(sortBy).descending()
            : Sort.by(sortBy).ascending();

        Pageable pageable = PageRequest.of(page, size, sort);
        return repo.findAll(pageable);
    }
}
```

### Page Object Response:

```json
{
  "content": [ ... ],
  "pageable": {
    "pageNumber": 0,
    "pageSize": 10,
    "sort": { "sorted": true, "orders": [{"property": "name", "direction": "ASC"}] }
  },
  "totalPages": 5,
  "totalElements": 47,
  "last": false,
  "first": true,
  "numberOfElements": 10,
  "size": 10,
  "number": 0
}
```

---

## Q76: What is the difference between Page and Slice?

| Aspect | `Page<T>` | `Slice<T>` |
|--------|-----------|------------|
| Total count | Yes (`getTotalElements()`, `getTotalPages()`) | No |
| SQL queries | **2 queries**: SELECT + COUNT | **1 query**: SELECT with limit+1 |
| Performance | Slower (extra COUNT query) | Faster |
| Use case | Traditional pagination with page numbers | Infinite scroll / "Load More" |
| Has next check | Based on total count | Fetches n+1 rows to check |

```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    Page<Product> findByCategory(String category, Pageable pageable);   // 2 queries
    Slice<Product> findByBrand(String brand, Pageable pageable);        // 1 query
}

// Using Page
Page<Product> page = repo.findByCategory("Electronics", PageRequest.of(0, 10));
page.getTotalElements();  // 150
page.getTotalPages();     // 15
page.hasNext();           // true
page.getContent();        // List<Product> of current page

// Using Slice
Slice<Product> slice = repo.findByBrand("Apple", PageRequest.of(0, 10));
// slice.getTotalElements() — NOT AVAILABLE
slice.hasNext();          // true (checked by fetching 11 rows)
slice.getContent();       // List<Product> of current page
```

**Rule of thumb:** Use `Slice` for large datasets or infinite scroll UIs. Use `Page` when you need to display total page count.

---

## Q77: What are Projections in Spring Data JPA? (Interface-based, Class-based, Dynamic)

Projections allow you to retrieve only specific fields instead of entire entities, improving performance.

### 1. Interface-based (Closed) Projection:

```java
// Define a projection interface
public interface EmployeeNameProjection {
    String getName();
    String getDepartment();

    // SpEL expression for computed value
    @Value("#{target.name + ' (' + target.department + ')'}")
    String getFullDescription();
}

public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    List<EmployeeNameProjection> findByDepartment(String department);
}

// Generated SQL: SELECT e.name, e.department FROM employees e WHERE e.department = ?
```

### 2. Interface-based (Open) Projection:

```java
public interface EmployeeProjection {
    @Value("#{target.firstName + ' ' + target.lastName}")
    String getFullName();
}
// NOTE: Open projections fetch all columns and compute in memory
```

### 3. Nested Projections:

```java
public interface OrderProjection {
    String getOrderNumber();
    CustomerProjection getCustomer();  // Nested projection

    interface CustomerProjection {
        String getName();
        String getEmail();
    }
}
```

### 4. Class-based (DTO) Projection:

```java
public class EmployeeDTO {
    private final String name;
    private final Double salary;

    // Constructor parameter names must match entity property names
    public EmployeeDTO(String name, Double salary) {
        this.name = name;
        this.salary = salary;
    }

    // Getters...
}

public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    List<EmployeeDTO> findByDepartment(String department);

    // Or with @Query
    @Query("SELECT new com.example.dto.EmployeeDTO(e.name, e.salary) FROM Employee e")
    List<EmployeeDTO> findAllDTOs();
}
```

### 5. Dynamic Projections:

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    // Generic type parameter determines projection
    <T> List<T> findByDepartment(String department, Class<T> type);
}

// Usage
List<EmployeeNameProjection> names = repo.findByDepartment("IT", EmployeeNameProjection.class);
List<EmployeeSalaryProjection> salaries = repo.findByDepartment("IT", EmployeeSalaryProjection.class);
List<Employee> full = repo.findByDepartment("IT", Employee.class);
```

---

## Q78: What is @EntityGraph? How does it solve N+1 problem?

The **N+1 problem** occurs when fetching an entity with lazy associations — 1 query fetches N entities, then N additional queries fetch each association.

`@EntityGraph` defines which associations should be fetched eagerly at query time, without changing the entity's default fetch strategy.

```java
@Entity
public class Employee {
    @Id
    private Long id;
    private String name;

    @ManyToOne(fetch = FetchType.LAZY)
    private Department department;

    @ManyToMany(fetch = FetchType.LAZY)
    private Set<Project> projects;
}
```

### Using @EntityGraph:

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // Attribute paths to fetch eagerly
    @EntityGraph(attributePaths = {"department", "projects"})
    List<Employee> findAll();

    // On custom query methods
    @EntityGraph(attributePaths = {"department"})
    List<Employee> findByName(String name);

    // On @Query methods
    @EntityGraph(attributePaths = {"department", "projects"})
    @Query("SELECT e FROM Employee e WHERE e.salary > :salary")
    List<Employee> findHighEarners(@Param("salary") Double salary);

    // Using a named entity graph defined on the entity
    @EntityGraph(value = "Employee.withDepartment", type = EntityGraph.EntityGraphType.FETCH)
    List<Employee> findByDepartmentName(String deptName);
}
```

### Named Entity Graph (defined on entity):

```java
@Entity
@NamedEntityGraph(
    name = "Employee.withDepartment",
    attributeNodes = @NamedAttributeNode("department")
)
@NamedEntityGraph(
    name = "Employee.full",
    attributeNodes = {
        @NamedAttributeNode("department"),
        @NamedAttributeNode(value = "projects", subgraph = "projects-subgraph")
    },
    subgraphs = @NamedSubgraph(
        name = "projects-subgraph",
        attributeNodes = @NamedAttributeNode("tasks")
    )
)
public class Employee { ... }
```

### EntityGraphType:

- **FETCH** — Attributes in the graph are EAGER, all others are LAZY
- **LOAD** — Attributes in the graph are EAGER, others use their default fetch type

### Without vs With @EntityGraph:

```sql
-- Without (N+1): 1 + N queries
SELECT * FROM employees;                    -- 1 query
SELECT * FROM departments WHERE id = ?;     -- N queries (for each employee)

-- With @EntityGraph: 1 JOIN query
SELECT e.*, d.* FROM employees e LEFT JOIN departments d ON e.dept_id = d.id;
```

---

## Q79: What is Specification in Spring Data JPA? How to build dynamic queries?

`Specification` implements the **Criteria API** in a reusable, composable way for building dynamic queries at runtime.

```java
// Repository must extend JpaSpecificationExecutor
public interface EmployeeRepository extends JpaRepository<Employee, Long>,
                                            JpaSpecificationExecutor<Employee> {
}
```

### Defining Specifications:

```java
public class EmployeeSpecifications {

    public static Specification<Employee> hasDepartment(String department) {
        return (root, query, cb) -> cb.equal(root.get("department"), department);
    }

    public static Specification<Employee> salaryGreaterThan(Double salary) {
        return (root, query, cb) -> cb.greaterThan(root.get("salary"), salary);
    }

    public static Specification<Employee> nameLike(String name) {
        return (root, query, cb) -> cb.like(root.get("name"), "%" + name + "%");
    }

    public static Specification<Employee> isActive() {
        return (root, query, cb) -> cb.isTrue(root.get("active"));
    }

    public static Specification<Employee> joinedAfter(LocalDate date) {
        return (root, query, cb) -> cb.greaterThan(root.get("joinDate"), date);
    }
}
```

### Composing Specifications:

```java
@Service
public class EmployeeService {

    @Autowired
    private EmployeeRepository repo;

    public List<Employee> search(EmployeeSearchCriteria criteria) {
        Specification<Employee> spec = Specification.where(null); // start empty

        if (criteria.getDepartment() != null) {
            spec = spec.and(EmployeeSpecifications.hasDepartment(criteria.getDepartment()));
        }
        if (criteria.getMinSalary() != null) {
            spec = spec.and(EmployeeSpecifications.salaryGreaterThan(criteria.getMinSalary()));
        }
        if (criteria.getName() != null) {
            spec = spec.and(EmployeeSpecifications.nameLike(criteria.getName()));
        }
        if (criteria.isActiveOnly()) {
            spec = spec.and(EmployeeSpecifications.isActive());
        }

        return repo.findAll(spec);
    }

    // With pagination
    public Page<Employee> searchPaged(EmployeeSearchCriteria criteria, Pageable pageable) {
        Specification<Employee> spec = buildSpec(criteria);
        return repo.findAll(spec, pageable);
    }
}
```

### JpaSpecificationExecutor Methods:

```java
public interface JpaSpecificationExecutor<T> {
    Optional<T> findOne(Specification<T> spec);
    List<T> findAll(Specification<T> spec);
    Page<T> findAll(Specification<T> spec, Pageable pageable);
    List<T> findAll(Specification<T> spec, Sort sort);
    long count(Specification<T> spec);
    boolean exists(Specification<T> spec);
}
```

---

## Q80: What is QueryByExampleExecutor?

Query by Example (QBE) allows you to query using an entity instance as a "probe" — fields with values become WHERE conditions, null fields are ignored.

```java
// JpaRepository already extends QueryByExampleExecutor
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    // No additional methods needed
}
```

### Usage:

```java
@Service
public class EmployeeService {

    @Autowired
    private EmployeeRepository repo;

    public List<Employee> searchByExample(String department, String name) {
        // Create probe entity
        Employee probe = new Employee();
        probe.setDepartment(department);
        probe.setName(name);
        // Null fields are ignored

        // Default matching
        Example<Employee> example = Example.of(probe);
        return repo.findAll(example);

        // Custom matching
        ExampleMatcher matcher = ExampleMatcher.matching()
            .withIgnoreCase()
            .withStringMatcher(ExampleMatcher.StringMatcher.CONTAINING)
            .withIgnorePaths("salary", "id") // Ignore these fields even if set
            .withMatcher("name", match -> match.startsWith());

        Example<Employee> example = Example.of(probe, matcher);
        return repo.findAll(example);
    }
}
```

### Limitations:

- No support for range queries (`>`, `<`, `BETWEEN`)
- No nested/grouped constraints (`(a AND b) OR c`)
- Only string matching for string properties
- Works best for simple filter-by-example use cases

For complex dynamic queries, use **Specifications** instead.

---

## Q81: What is Auditing in Spring Data JPA? (@CreatedDate, @LastModifiedDate, @CreatedBy, @LastModifiedBy)

Auditing automatically populates creation/modification timestamps and user information on entities.

### Setup:

```java
// 1. Enable JPA Auditing
@Configuration
@EnableJpaAuditing(auditorAwareRef = "auditorProvider")
public class JpaConfig {

    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext())
                .map(SecurityContext::getAuthentication)
                .filter(Authentication::isAuthenticated)
                .map(Authentication::getName);
    }
}

// 2. Create a base entity with audit fields
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class Auditable {

    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    private LocalDateTime updatedAt;

    @CreatedBy
    @Column(updatable = false)
    private String createdBy;

    @LastModifiedBy
    private String updatedBy;

    // Getters and setters
}

// 3. Extend in your entities
@Entity
public class Employee extends Auditable {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    // ...
}
```

### Alternative — Using `@Embedded`:

```java
@Embeddable
@EntityListeners(AuditingEntityListener.class)
public class AuditMetadata {
    @CreatedDate
    private Instant createdAt;

    @LastModifiedDate
    private Instant modifiedAt;
}

@Entity
public class Order {
    @Id
    private Long id;

    @Embedded
    private AuditMetadata audit = new AuditMetadata();
}
```

---

## Q82: How to implement soft delete in Spring Data JPA?

Soft delete marks records as deleted without physically removing them from the database.

### Implementation:

```java
@Entity
@Where(clause = "deleted = false")  // Hibernate-specific: auto-filter
@SQLDelete(sql = "UPDATE employees SET deleted = true WHERE id = ?")  // Override DELETE SQL
public class Employee {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;

    private boolean deleted = false;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;
}
```

### Repository with soft delete support:

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // @Where clause automatically filters deleted records in all queries

    // Explicitly find including deleted
    @Query("SELECT e FROM Employee e WHERE e.id = :id")
    @Where(clause = "")  // Won't work — use native
    Optional<Employee> findByIdIncludingDeleted(@Param("id") Long id);

    // Native query to bypass @Where filter
    @Query(value = "SELECT * FROM employees WHERE id = :id", nativeQuery = true)
    Optional<Employee> findByIdIncludingDeleted(@Param("id") Long id);

    // Find all deleted records
    @Query(value = "SELECT * FROM employees WHERE deleted = true", nativeQuery = true)
    List<Employee> findAllDeleted();
}
```

### Alternative without Hibernate annotations (pure Spring Data):

```java
@Entity
public class Employee {
    @Id
    private Long id;
    private String name;
    private boolean deleted = false;
}

public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // Override default methods to filter
    @Override
    @Query("SELECT e FROM Employee e WHERE e.deleted = false")
    List<Employee> findAll();

    @Query("SELECT e FROM Employee e WHERE e.id = :id AND e.deleted = false")
    Optional<Employee> findActiveById(@Param("id") Long id);

    // Soft delete method
    @Modifying
    @Query("UPDATE Employee e SET e.deleted = true, e.deletedAt = CURRENT_TIMESTAMP WHERE e.id = :id")
    void softDelete(@Param("id") Long id);
}
```

---

## Q83: What is @Lock annotation? Explain pessimistic vs optimistic locking

`@Lock` specifies the lock mode for a query method, controlling concurrent access to data.

### Optimistic Locking (using @Version):

- No database lock acquired
- Uses a version field; if version mismatch on update → `OptimisticLockException`
- Best for read-heavy workloads with rare conflicts

### Pessimistic Locking (using @Lock):

- Acquires actual database lock (SELECT ... FOR UPDATE)
- Blocks other transactions from reading/writing
- Best for high-contention scenarios

```java
public interface AccountRepository extends JpaRepository<Account, Long> {

    // Pessimistic Write Lock - blocks reads and writes
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.id = :id")
    Optional<Account> findByIdForUpdate(@Param("id") Long id);

    // Pessimistic Read Lock - allows other reads, blocks writes
    @Lock(LockModeType.PESSIMISTIC_READ)
    Optional<Account> findById(Long id);

    // Optimistic Lock - checks version on read
    @Lock(LockModeType.OPTIMISTIC)
    @Query("SELECT a FROM Account a WHERE a.id = :id")
    Optional<Account> findByIdOptimistic(@Param("id") Long id);

    // OPTIMISTIC_FORCE_INCREMENT - increments version even on read
    @Lock(LockModeType.OPTIMISTIC_FORCE_INCREMENT)
    Optional<Account> findByAccountNumber(String accountNumber);
}
```

### Lock Modes:

| LockModeType | SQL Generated | Use Case |
|-------------|---------------|----------|
| `PESSIMISTIC_READ` | `SELECT ... FOR SHARE` | Allow reads, block writes |
| `PESSIMISTIC_WRITE` | `SELECT ... FOR UPDATE` | Block reads and writes |
| `PESSIMISTIC_FORCE_INCREMENT` | `FOR UPDATE` + version++ | Lock + version bump |
| `OPTIMISTIC` | Check version at commit | Detect concurrent modifications |
| `OPTIMISTIC_FORCE_INCREMENT` | Increment version on read | Force conflict detection |

### Usage in service:

```java
@Service
public class TransferService {

    @Transactional
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        // Pessimistic lock prevents race conditions
        Account from = accountRepo.findByIdForUpdate(fromId)
            .orElseThrow();
        Account to = accountRepo.findByIdForUpdate(toId)
            .orElseThrow();

        from.debit(amount);
        to.credit(amount);
    }
}
```

---

## Q84: What is @Version for optimistic locking?

`@Version` marks a field that JPA uses to detect concurrent modifications. On each update, JPA checks that the version hasn't changed since the entity was read.

```java
@Entity
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private Double price;

    @Version
    private Integer version;  // Supported types: int, Integer, long, Long, short, Short, Timestamp
}
```

### How it works:

```sql
-- When updating, JPA adds version check:
UPDATE products SET name = ?, price = ?, version = 2
WHERE id = 1 AND version = 1;

-- If another transaction already changed version to 2:
-- 0 rows updated → JPA throws OptimisticLockException
```

### Handling the exception:

```java
@Service
public class ProductService {

    @Transactional
    public void updatePrice(Long productId, Double newPrice) {
        Product product = repo.findById(productId).orElseThrow();
        product.setPrice(newPrice);
        // On save, if version mismatch → OptimisticLockException
    }

    // Retry pattern
    @Retryable(value = OptimisticLockException.class, maxAttempts = 3)
    @Transactional
    public void updatePriceWithRetry(Long productId, Double newPrice) {
        Product product = repo.findById(productId).orElseThrow();
        product.setPrice(newPrice);
    }
}

// Controller-level handling
@ExceptionHandler(OptimisticLockException.class)
public ResponseEntity<?> handleOptimisticLock(OptimisticLockException ex) {
    return ResponseEntity.status(HttpStatus.CONFLICT)
        .body("Resource was modified by another user. Please retry.");
}
```

---

## Q85: How to call stored procedures from Spring Data JPA?

### Method 1: @Procedure annotation

```java
// Stored procedure in database:
// CREATE PROCEDURE calculate_bonus(IN emp_id BIGINT, OUT bonus DOUBLE)

@Entity
@NamedStoredProcedureQuery(
    name = "Employee.calculateBonus",
    procedureName = "calculate_bonus",
    parameters = {
        @StoredProcedureParameter(mode = ParameterMode.IN, name = "emp_id", type = Long.class),
        @StoredProcedureParameter(mode = ParameterMode.OUT, name = "bonus", type = Double.class)
    }
)
public class Employee { ... }

public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    // Reference by stored procedure name
    @Procedure(procedureName = "calculate_bonus")
    Double calculateBonus(@Param("emp_id") Long employeeId);

    // Reference by named stored procedure query
    @Procedure(name = "Employee.calculateBonus")
    Double getBonus(@Param("emp_id") Long employeeId);
}
```

### Method 2: @Query with native call

```java
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    @Query(value = "CALL get_employees_by_dept(:dept)", nativeQuery = true)
    List<Employee> getByDepartment(@Param("dept") String department);
}
```

### Method 3: EntityManager directly

```java
@Repository
public class EmployeeCustomRepo {

    @PersistenceContext
    private EntityManager em;

    public Double calculateBonus(Long empId) {
        StoredProcedureQuery query = em.createStoredProcedureQuery("calculate_bonus");
        query.registerStoredProcedureParameter("emp_id", Long.class, ParameterMode.IN);
        query.registerStoredProcedureParameter("bonus", Double.class, ParameterMode.OUT);
        query.setParameter("emp_id", empId);
        query.execute();
        return (Double) query.getOutputParameterValue("bonus");
    }
}
```

---

## Q86: What is custom repository implementation in Spring Data JPA?

Custom repository implementation allows you to add methods with hand-written logic while keeping the benefits of Spring Data's auto-generated methods.

### Pattern:

```java
// 1. Define custom interface
public interface EmployeeRepositoryCustom {
    List<Employee> findByComplexCriteria(SearchFilter filter);
    void bulkInsert(List<Employee> employees);
}

// 2. Implement it (naming convention: <RepositoryName>Impl)
@Repository
public class EmployeeRepositoryImpl implements EmployeeRepositoryCustom {

    @PersistenceContext
    private EntityManager em;

    @Override
    public List<Employee> findByComplexCriteria(SearchFilter filter) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
        Root<Employee> root = cq.from(Employee.class);

        List<Predicate> predicates = new ArrayList<>();
        // Build dynamic predicates...

        cq.where(predicates.toArray(new Predicate[0]));
        return em.createQuery(cq).getResultList();
    }

    @Override
    public void bulkInsert(List<Employee> employees) {
        for (int i = 0; i < employees.size(); i++) {
            em.persist(employees.get(i));
            if (i % 50 == 0) {
                em.flush();
                em.clear();
            }
        }
    }
}

// 3. Extend both interfaces in main repository
public interface EmployeeRepository extends JpaRepository<Employee, Long>,
                                            EmployeeRepositoryCustom {
    // Spring Data methods
    List<Employee> findByDepartment(String dept);
    // Custom methods from EmployeeRepositoryCustom are also available
}
```

### Usage:

```java
@Service
public class EmployeeService {
    @Autowired
    private EmployeeRepository repo; // Has both Spring Data + custom methods

    public void doStuff() {
        repo.findByDepartment("IT");          // Spring Data derived
        repo.findByComplexCriteria(filter);    // Custom implementation
        repo.findAll();                        // JpaRepository
    }
}
```

> **Note:** The implementation class must be named `<RepositoryInterface>Impl` by default. You can change the suffix with `@EnableJpaRepositories(repositoryImplementationPostfix = "CustomImpl")`.

---

## Q87: How does Spring Data JPA auto-configuration work in Spring Boot?

Spring Boot auto-configures Spring Data JPA when it detects `spring-boot-starter-data-jpa` on the classpath.

### What happens automatically:

1. **DataSource** — Configured from `spring.datasource.*` properties
2. **EntityManagerFactory** — Created using Hibernate as the JPA provider
3. **TransactionManager** — `JpaTransactionManager` bean registered
4. **Repository scanning** — `@EnableJpaRepositories` applied to the main application package
5. **Entity scanning** — `@EntityScan` applied to the main application package

### Key auto-configuration classes:

- `DataSourceAutoConfiguration` — Sets up connection pool (HikariCP default)
- `HibernateJpaAutoConfiguration` — Configures Hibernate as JPA provider
- `JpaRepositoriesAutoConfiguration` — Enables repository scanning

### Common properties:

```properties
# DataSource
spring.datasource.url=jdbc:postgresql://localhost:5432/mydb
spring.datasource.username=user
spring.datasource.password=pass
spring.datasource.driver-class-name=org.postgresql.Driver

# JPA/Hibernate
spring.jpa.database-platform=org.hibernate.dialect.PostgreSQLDialect
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true
spring.jpa.properties.hibernate.default_batch_fetch_size=20
spring.jpa.properties.hibernate.jdbc.batch_size=30
spring.jpa.properties.hibernate.order_inserts=true
spring.jpa.properties.hibernate.order_updates=true

# Connection Pool (HikariCP)
spring.datasource.hikari.maximum-pool-size=20
spring.datasource.hikari.minimum-idle=5
spring.datasource.hikari.idle-timeout=300000
```

### Overriding auto-configuration:

```java
@Configuration
public class CustomJpaConfig {

    // Define your own EntityManagerFactory to override auto-config
    @Bean
    public LocalContainerEntityManagerFactoryBean entityManagerFactory(
            DataSource dataSource) {
        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(dataSource);
        em.setPackagesToScan("com.example.entities");
        em.setJpaVendorAdapter(new HibernateJpaVendorAdapter());
        return em;
    }
}
```

---

## Q88: What is spring.jpa.open-in-view and why should you disable it?

`spring.jpa.open-in-view` (OSIV — Open Session In View) keeps the Hibernate Session open for the entire HTTP request lifecycle, allowing lazy loading in the view/controller layer.

### Default: `true` (enabled)

```
Request → Filter opens Session → Controller → Service → Repository → Controller → View renders (lazy load here) → Filter closes Session
```

### Why you should disable it:

1. **Database connections held longer** — Session (and connection) open for entire request including view rendering
2. **N+1 in controllers** — Lazy loading in controllers/views causes unpredictable queries
3. **Tight coupling** — View layer depends on JPA session being open
4. **Performance** — Connection pool exhaustion under load
5. **Unpredictable behavior** — Queries execute outside transactional boundaries

```properties
# Disable OSIV
spring.jpa.open-in-view=false
```

### After disabling:

```java
// This will throw LazyInitializationException if accessed outside transaction
@GetMapping("/employees/{id}")
public Employee getEmployee(@PathVariable Long id) {
    Employee emp = repo.findById(id).orElseThrow();
    emp.getDepartment().getName(); // LazyInitializationException!
    return emp;
}

// Solutions:
// 1. Use @EntityGraph
@EntityGraph(attributePaths = "department")
Optional<Employee> findById(Long id);

// 2. Use JOIN FETCH in @Query
@Query("SELECT e FROM Employee e JOIN FETCH e.department WHERE e.id = :id")
Optional<Employee> findByIdWithDepartment(@Param("id") Long id);

// 3. Use DTOs/Projections
// 4. Initialize in service layer within @Transactional
```

**Best practice:** Always disable OSIV and explicitly fetch what you need.

---

## Q89: How to handle multiple datasources in Spring Data JPA?

```java
// application.properties
spring.datasource.primary.url=jdbc:mysql://localhost:3306/primary_db
spring.datasource.primary.username=root
spring.datasource.primary.password=pass

spring.datasource.secondary.url=jdbc:postgresql://localhost:5432/secondary_db
spring.datasource.secondary.username=user
spring.datasource.secondary.password=pass
```

### Configuration:

```java
// Primary DataSource Configuration
@Configuration
@EnableJpaRepositories(
    basePackages = "com.example.repository.primary",
    entityManagerFactoryRef = "primaryEntityManagerFactory",
    transactionManagerRef = "primaryTransactionManager"
)
public class PrimaryDataSourceConfig {

    @Primary
    @Bean
    @ConfigurationProperties("spring.datasource.primary")
    public DataSourceProperties primaryDataSourceProperties() {
        return new DataSourceProperties();
    }

    @Primary
    @Bean
    public DataSource primaryDataSource() {
        return primaryDataSourceProperties()
            .initializeDataSourceBuilder()
            .type(HikariDataSource.class)
            .build();
    }

    @Primary
    @Bean
    public LocalContainerEntityManagerFactoryBean primaryEntityManagerFactory(
            EntityManagerFactoryBuilder builder) {
        return builder
            .dataSource(primaryDataSource())
            .packages("com.example.entity.primary")
            .persistenceUnit("primary")
            .build();
    }

    @Primary
    @Bean
    public PlatformTransactionManager primaryTransactionManager(
            @Qualifier("primaryEntityManagerFactory") EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }
}

// Secondary DataSource Configuration
@Configuration
@EnableJpaRepositories(
    basePackages = "com.example.repository.secondary",
    entityManagerFactoryRef = "secondaryEntityManagerFactory",
    transactionManagerRef = "secondaryTransactionManager"
)
public class SecondaryDataSourceConfig {

    @Bean
    @ConfigurationProperties("spring.datasource.secondary")
    public DataSourceProperties secondaryDataSourceProperties() {
        return new DataSourceProperties();
    }

    @Bean
    public DataSource secondaryDataSource() {
        return secondaryDataSourceProperties()
            .initializeDataSourceBuilder()
            .type(HikariDataSource.class)
            .build();
    }

    @Bean
    public LocalContainerEntityManagerFactoryBean secondaryEntityManagerFactory(
            EntityManagerFactoryBuilder builder) {
        return builder
            .dataSource(secondaryDataSource())
            .packages("com.example.entity.secondary")
            .persistenceUnit("secondary")
            .build();
    }

    @Bean
    public PlatformTransactionManager secondaryTransactionManager(
            @Qualifier("secondaryEntityManagerFactory") EntityManagerFactory emf) {
        return new JpaTransactionManager(emf);
    }
}
```

### Package structure:

```
com.example
├── entity
│   ├── primary/     → Employee.java, Department.java
│   └── secondary/   → AuditLog.java, Report.java
├── repository
│   ├── primary/     → EmployeeRepository.java
│   └── secondary/   → AuditLogRepository.java
```

### Using specific transaction manager:

```java
@Service
public class MyService {

    @Transactional("primaryTransactionManager")
    public void doPrimaryWork() { ... }

    @Transactional("secondaryTransactionManager")
    public void doSecondaryWork() { ... }
}
```

---

## Q90: What is @EnableJpaRepositories and its configuration?

`@EnableJpaRepositories` activates Spring Data JPA repository support by scanning for repository interfaces and creating proxy implementations.

```java
@Configuration
@EnableJpaRepositories(
    // Package(s) to scan for repositories
    basePackages = "com.example.repository",

    // Type-safe alternative to basePackages
    basePackageClasses = EmployeeRepository.class,

    // Which EntityManagerFactory to use
    entityManagerFactoryRef = "entityManagerFactory",

    // Which TransactionManager to use
    transactionManagerRef = "transactionManager",

    // Custom implementation suffix (default: "Impl")
    repositoryImplementationPostfix = "Impl",

    // Custom base repository class
    repositoryBaseClass = CustomJpaRepository.class,

    // Include/exclude filters
    includeFilters = @ComponentScan.Filter(type = FilterType.ANNOTATION, classes = MyRepo.class),
    excludeFilters = @ComponentScan.Filter(type = FilterType.REGEX, pattern = ".*Legacy.*"),

    // Named queries location
    namedQueriesLocation = "classpath:jpa-named-queries.properties",

    // Query lookup strategy
    queryLookupStrategy = QueryLookupStrategy.Key.CREATE_IF_NOT_FOUND
)
public class JpaConfig { }
```

### Query Lookup Strategies:

| Strategy | Behavior |
|----------|----------|
| `CREATE` | Derives query from method name only |
| `USE_DECLARED_QUERY` | Uses `@Query` or named queries only; fails if not found |
| `CREATE_IF_NOT_FOUND` | (Default) Tries declared query first, falls back to derived |

### Custom Base Repository:

```java
// Custom base implementation
public class CustomJpaRepository<T, ID> extends SimpleJpaRepository<T, ID> {

    private final EntityManager em;

    public CustomJpaRepository(JpaEntityInformation<T, ?> entityInfo, EntityManager em) {
        super(entityInfo, em);
        this.em = em;
    }

    // Add custom methods available to ALL repositories
    public void refresh(T entity) {
        em.refresh(entity);
    }
}

// All repositories now have refresh() method
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    // refresh() is available from CustomJpaRepository
}
```

### In Spring Boot:

Spring Boot auto-applies `@EnableJpaRepositories` to the main application package. You only need to explicitly use it when:

- Repositories are outside the main package
- Multiple datasources are configured
- Custom configuration is needed (base class, filters, etc.)
