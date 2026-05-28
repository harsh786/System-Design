# Querying - JPQL, Criteria API & Native Queries (Q91-Q115)

---

## Q91: What is JPQL? How is it different from SQL?

**JPQL (Java Persistence Query Language)** is an object-oriented query language defined by JPA that operates on **entities and their fields**, not database tables and columns.

### Key Differences

| Aspect | JPQL | SQL |
|--------|------|-----|
| Operates on | Entities/Objects | Tables/Rows |
| References | Class names, field names | Table names, column names |
| Portability | Database-independent | Database-specific |
| Relationships | Navigated via object references | Requires explicit JOINs |
| Result | Entities or projections | Rows and columns |

### Example

```java
// JPQL - uses entity name and field names
String jpql = "SELECT e FROM Employee e WHERE e.department.name = :deptName";

// Equivalent SQL
String sql = "SELECT * FROM employees e JOIN departments d ON e.dept_id = d.id WHERE d.name = ?";
```

JPQL is translated by the JPA provider (Hibernate) into native SQL for the target database.

---

## Q92: Write JPQL for basic SELECT, WHERE, ORDER BY

```java
// Basic SELECT - all employees
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e", Employee.class);
List<Employee> employees = query.getResultList();

// WHERE clause with parameters
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e WHERE e.salary > :minSalary AND e.active = true",
    Employee.class);
query.setParameter("minSalary", 50000.0);
List<Employee> results = query.getResultList();

// ORDER BY
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e WHERE e.department.name = :dept ORDER BY e.lastName ASC, e.firstName ASC",
    Employee.class);
query.setParameter("dept", "Engineering");

// Selecting specific fields
TypedQuery<String> query = em.createQuery(
    "SELECT e.email FROM Employee e WHERE e.active = true", String.class);

// DISTINCT
TypedQuery<String> query = em.createQuery(
    "SELECT DISTINCT e.department.name FROM Employee e", String.class);

// Positional parameters
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e WHERE e.salary BETWEEN ?1 AND ?2", Employee.class);
query.setParameter(1, 40000.0);
query.setParameter(2, 80000.0);
```

---

## Q93: How to use JOIN and FETCH JOIN in JPQL?

### Implicit JOIN (path navigation)

```java
// Implicit join via dot notation
String jpql = "SELECT e FROM Employee e WHERE e.department.name = 'Engineering'";
```

### Explicit JOIN

```java
// INNER JOIN
String jpql = "SELECT e FROM Employee e JOIN e.department d WHERE d.location = 'NYC'";

// LEFT JOIN
String jpql = "SELECT e FROM Employee e LEFT JOIN e.projects p WHERE p.status = 'ACTIVE'";

// JOIN with ON clause (JPA 2.1+)
String jpql = "SELECT e FROM Employee e JOIN e.projects p ON p.startDate > :date";
```

### FETCH JOIN

```java
// Fetch join eagerly loads the association in one query
String jpql = "SELECT e FROM Employee e JOIN FETCH e.department";

// Left fetch join
String jpql = "SELECT e FROM Employee e LEFT JOIN FETCH e.projects WHERE e.active = true";

// Multiple fetch joins
String jpql = "SELECT DISTINCT e FROM Employee e " +
    "JOIN FETCH e.department " +
    "LEFT JOIN FETCH e.addresses";
```

```java
TypedQuery<Employee> query = em.createQuery(
    "SELECT DISTINCT e FROM Employee e JOIN FETCH e.projects p WHERE p.status = :status",
    Employee.class);
query.setParameter("status", ProjectStatus.ACTIVE);
List<Employee> employees = query.getResultList();
// employees.getProjects() is already loaded - no lazy loading needed
```

---

## Q94: What is the difference between JOIN and FETCH JOIN?

| Aspect | JOIN | FETCH JOIN |
|--------|------|------------|
| Purpose | Filtering/conditions | Eager loading associations |
| SQL Generated | Regular JOIN | JOIN with all columns selected |
| Lazy Loading | Association still lazy | Association loaded immediately |
| Result | Only root entity populated | Root + joined entity populated |
| Pagination | Works normally | Problematic with collections |

### Example demonstrating the difference

```java
// Regular JOIN - department is NOT loaded (still lazy)
TypedQuery<Employee> q1 = em.createQuery(
    "SELECT e FROM Employee e JOIN e.department d WHERE d.name = 'IT'", Employee.class);
List<Employee> list1 = q1.getResultList();
// Accessing list1.get(0).getDepartment().getName() triggers another SQL query (N+1)

// FETCH JOIN - department IS loaded
TypedQuery<Employee> q2 = em.createQuery(
    "SELECT e FROM Employee e JOIN FETCH e.department d WHERE d.name = 'IT'", Employee.class);
List<Employee> list2 = q2.getResultList();
// Accessing list2.get(0).getDepartment().getName() uses already-loaded data
```

### Important caveats with FETCH JOIN

```java
// Cannot use FETCH JOIN with pagination on collections (causes in-memory pagination warning)
// BAD:
em.createQuery("SELECT e FROM Employee e JOIN FETCH e.phoneNumbers")
    .setFirstResult(0)
    .setMaxResults(10)
    .getResultList();
// Hibernate WARNING: firstResult/maxResults specified with collection fetch; applying in memory!

// GOOD: Use two-query approach
List<Long> ids = em.createQuery(
    "SELECT e.id FROM Employee e ORDER BY e.id", Long.class)
    .setFirstResult(0).setMaxResults(10).getResultList();

List<Employee> employees = em.createQuery(
    "SELECT DISTINCT e FROM Employee e JOIN FETCH e.phoneNumbers WHERE e.id IN :ids", Employee.class)
    .setParameter("ids", ids).getResultList();
```

---

## Q95: How to use aggregate functions in JPQL (COUNT, SUM, AVG, MIN, MAX)?

```java
// COUNT
Long count = em.createQuery(
    "SELECT COUNT(e) FROM Employee e WHERE e.active = true", Long.class)
    .getSingleResult();

// SUM
Double totalSalary = em.createQuery(
    "SELECT SUM(e.salary) FROM Employee e WHERE e.department.name = :dept", Double.class)
    .setParameter("dept", "Engineering")
    .getSingleResult();

// AVG
Double avgSalary = em.createQuery(
    "SELECT AVG(e.salary) FROM Employee e", Double.class)
    .getSingleResult();

// MIN and MAX
Object[] result = em.createQuery(
    "SELECT MIN(e.salary), MAX(e.salary) FROM Employee e", Object[].class)
    .getSingleResult();
Double minSalary = (Double) result[0];
Double maxSalary = (Double) result[1];

// COUNT with DISTINCT
Long distinctDepts = em.createQuery(
    "SELECT COUNT(DISTINCT e.department) FROM Employee e", Long.class)
    .getSingleResult();

// Multiple aggregates
List<Object[]> stats = em.createQuery(
    "SELECT e.department.name, COUNT(e), AVG(e.salary), MAX(e.salary) " +
    "FROM Employee e GROUP BY e.department.name", Object[].class)
    .getResultList();

for (Object[] row : stats) {
    String deptName = (String) row[0];
    Long empCount = (Long) row[1];
    Double avgSal = (Double) row[2];
    Double maxSal = (Double) row[3];
}
```

---

## Q96: How to use GROUP BY and HAVING in JPQL?

```java
// GROUP BY
List<Object[]> results = em.createQuery(
    "SELECT e.department.name, COUNT(e) FROM Employee e GROUP BY e.department.name",
    Object[].class)
    .getResultList();

// GROUP BY with HAVING
List<Object[]> results = em.createQuery(
    "SELECT e.department.name, AVG(e.salary) " +
    "FROM Employee e " +
    "GROUP BY e.department.name " +
    "HAVING AVG(e.salary) > :threshold",
    Object[].class)
    .setParameter("threshold", 60000.0)
    .getResultList();

// Multiple GROUP BY columns
List<Object[]> results = em.createQuery(
    "SELECT e.department.name, e.role, COUNT(e) " +
    "FROM Employee e " +
    "GROUP BY e.department.name, e.role " +
    "HAVING COUNT(e) > 5 " +
    "ORDER BY e.department.name",
    Object[].class)
    .getResultList();

// Using with DTO projection
List<DepartmentStats> stats = em.createQuery(
    "SELECT NEW com.example.dto.DepartmentStats(d.name, COUNT(e), AVG(e.salary)) " +
    "FROM Employee e JOIN e.department d " +
    "GROUP BY d.name " +
    "HAVING COUNT(e) >= :minCount",
    DepartmentStats.class)
    .setParameter("minCount", 3L)
    .getResultList();
```

---

## Q97: What are named queries (@NamedQuery)? What are their advantages?

**Named queries** are statically defined, reusable queries declared on the entity class. They are **parsed and validated at application startup**.

```java
@Entity
@NamedQueries({
    @NamedQuery(
        name = "Employee.findAll",
        query = "SELECT e FROM Employee e ORDER BY e.lastName"
    ),
    @NamedQuery(
        name = "Employee.findByDepartment",
        query = "SELECT e FROM Employee e WHERE e.department.name = :deptName"
    ),
    @NamedQuery(
        name = "Employee.findHighEarners",
        query = "SELECT e FROM Employee e WHERE e.salary > :threshold",
        hints = @QueryHint(name = "org.hibernate.cacheable", value = "true")
    )
})
public class Employee {
    // ...
}
```

### Usage

```java
List<Employee> employees = em.createNamedQuery("Employee.findByDepartment", Employee.class)
    .setParameter("deptName", "Engineering")
    .getResultList();
```

### Advantages

1. **Early validation** - Syntax errors caught at startup, not runtime
2. **Pre-compiled** - Query parsed once, reused many times (performance)
3. **Centralized** - All queries for an entity in one place
4. **Cacheable** - Provider can cache the query plan
5. **Maintainable** - Easy to find and modify queries

### Disadvantages

- Not dynamic - cannot build query conditionally at runtime
- Clutters entity class with many annotations

---

## Q98: What is @NamedNativeQuery?

`@NamedNativeQuery` defines a **native SQL** query (not JPQL) as a named query on an entity. Used when you need database-specific SQL features.

```java
@Entity
@NamedNativeQueries({
    @NamedNativeQuery(
        name = "Employee.findByNativeSQL",
        query = "SELECT * FROM employees WHERE hire_date > :date",
        resultClass = Employee.class
    ),
    @NamedNativeQuery(
        name = "Employee.getDeptStats",
        query = "SELECT d.name as dept_name, COUNT(*) as emp_count, AVG(e.salary) as avg_salary " +
                "FROM employees e JOIN departments d ON e.dept_id = d.id " +
                "GROUP BY d.name",
        resultSetMapping = "DeptStatsMapping"
    )
})
@SqlResultSetMapping(
    name = "DeptStatsMapping",
    columns = {
        @ColumnResult(name = "dept_name", type = String.class),
        @ColumnResult(name = "emp_count", type = Long.class),
        @ColumnResult(name = "avg_salary", type = Double.class)
    }
)
public class Employee {
    // ...
}
```

### Usage

```java
List<Employee> employees = em.createNamedQuery("Employee.findByNativeSQL", Employee.class)
    .setParameter("date", LocalDate.of(2023, 1, 1))
    .getResultList();

List<Object[]> stats = em.createNamedQuery("Employee.getDeptStats")
    .getResultList();
```

### When to use

- Database-specific features (window functions, CTEs, hints)
- Complex queries that JPQL cannot express
- Performance-critical queries needing hand-tuned SQL
- Stored procedure calls

---

## Q99: How to use subqueries in JPQL?

```java
// Subquery in WHERE clause
String jpql = "SELECT e FROM Employee e " +
    "WHERE e.salary > (SELECT AVG(e2.salary) FROM Employee e2)";

// Correlated subquery
String jpql = "SELECT e FROM Employee e " +
    "WHERE e.salary > (SELECT AVG(e2.salary) FROM Employee e2 WHERE e2.department = e.department)";

// EXISTS subquery
String jpql = "SELECT d FROM Department d " +
    "WHERE EXISTS (SELECT e FROM Employee e WHERE e.department = d AND e.salary > 100000)";

// NOT EXISTS
String jpql = "SELECT d FROM Department d " +
    "WHERE NOT EXISTS (SELECT e FROM Employee e WHERE e.department = d)";

// IN with subquery
String jpql = "SELECT e FROM Employee e " +
    "WHERE e.department IN (SELECT d FROM Department d WHERE d.location = 'NYC')";

// ALL / ANY
String jpql = "SELECT e FROM Employee e " +
    "WHERE e.salary >= ALL (SELECT e2.salary FROM Employee e2 WHERE e2.department.name = 'Sales')";

String jpql = "SELECT e FROM Employee e " +
    "WHERE e.salary > ANY (SELECT e2.salary FROM Employee e2 WHERE e2.department.name = 'Marketing')";
```

```java
// Practical example: Employees who earn more than their department average
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e " +
    "WHERE e.salary > (SELECT AVG(e2.salary) FROM Employee e2 " +
    "WHERE e2.department = e.department)",
    Employee.class);
List<Employee> aboveAverage = query.getResultList();
```

---

## Q100: What is the Criteria API? Why use it over JPQL?

The **Criteria API** is a programmatic, type-safe way to build queries using Java objects instead of query strings. Defined in `javax.persistence.criteria` / `jakarta.persistence.criteria`.

### Why use Criteria API over JPQL?

| Scenario | JPQL | Criteria API |
|----------|------|--------------|
| Static queries | Preferred (simpler) | Overkill |
| Dynamic queries | String concatenation (error-prone) | Preferred (type-safe) |
| Compile-time safety | No (strings) | Yes (with metamodel) |
| Complex conditional filters | Messy | Clean and composable |

### Primary use case: Dynamic queries

```java
// Dynamic search with optional filters - Criteria API shines here
public List<Employee> searchEmployees(String name, String dept, Double minSalary, Boolean active) {
    CriteriaBuilder cb = em.getCriteriaBuilder();
    CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
    Root<Employee> root = cq.from(Employee.class);

    List<Predicate> predicates = new ArrayList<>();

    if (name != null) {
        predicates.add(cb.like(root.get("lastName"), "%" + name + "%"));
    }
    if (dept != null) {
        predicates.add(cb.equal(root.get("department").get("name"), dept));
    }
    if (minSalary != null) {
        predicates.add(cb.greaterThan(root.get("salary"), minSalary));
    }
    if (active != null) {
        predicates.add(cb.equal(root.get("active"), active));
    }

    cq.where(predicates.toArray(new Predicate[0]));
    return em.createQuery(cq).getResultList();
}
```

The equivalent in JPQL would require messy string concatenation with `WHERE 1=1 AND ...` patterns.

---

## Q101: How to build a simple Criteria query?

```java
// Step 1: Get CriteriaBuilder from EntityManager
CriteriaBuilder cb = em.getCriteriaBuilder();

// Step 2: Create CriteriaQuery specifying result type
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);

// Step 3: Define the FROM clause (root entity)
Root<Employee> root = cq.from(Employee.class);

// Step 4: Define SELECT
cq.select(root);

// Step 5: Add WHERE clause
cq.where(cb.equal(root.get("active"), true));

// Step 6: Add ORDER BY
cq.orderBy(cb.asc(root.get("lastName")));

// Step 7: Execute
TypedQuery<Employee> query = em.createQuery(cq);
List<Employee> results = query.getResultList();
```

### More complete example

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// SELECT e FROM Employee e WHERE e.salary > 50000 AND e.department.name = 'IT' ORDER BY e.salary DESC
cq.select(emp)
  .where(
      cb.and(
          cb.greaterThan(emp.get("salary"), 50000.0),
          cb.equal(emp.get("department").get("name"), "IT")
      )
  )
  .orderBy(cb.desc(emp.get("salary")));

List<Employee> results = em.createQuery(cq).getResultList();
```

### Selecting specific columns (multiselect)

```java
CriteriaQuery<Object[]> cq = cb.createQuery(Object[].class);
Root<Employee> emp = cq.from(Employee.class);
cq.multiselect(emp.get("firstName"), emp.get("lastName"), emp.get("salary"));

List<Object[]> results = em.createQuery(cq).getResultList();
```

---

## Q102: How to use CriteriaBuilder predicates (equal, like, between, in)?

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// EQUAL
Predicate eqPredicate = cb.equal(emp.get("status"), Status.ACTIVE);

// NOT EQUAL
Predicate neqPredicate = cb.notEqual(emp.get("role"), "INTERN");

// LIKE
Predicate likePredicate = cb.like(emp.get("email"), "%@company.com");
Predicate likeIgnoreCase = cb.like(cb.lower(emp.get("lastName")), "%smith%");

// BETWEEN
Predicate betweenPredicate = cb.between(emp.get("salary"), 40000.0, 80000.0);

// IN
List<String> departments = Arrays.asList("IT", "Engineering", "Data");
Predicate inPredicate = emp.get("department").get("name").in(departments);

// Greater than / Less than
Predicate gt = cb.greaterThan(emp.get("hireDate"), LocalDate.of(2020, 1, 1));
Predicate lt = cb.lessThanOrEqualTo(emp.get("salary"), 100000.0);

// IS NULL / IS NOT NULL
Predicate isNull = cb.isNull(emp.get("manager"));
Predicate isNotNull = cb.isNotNull(emp.get("email"));

// Combining predicates
Predicate andPredicate = cb.and(eqPredicate, likePredicate, betweenPredicate);
Predicate orPredicate = cb.or(inPredicate, gt);
Predicate notPredicate = cb.not(isNull);

// Final query
cq.select(emp).where(cb.and(andPredicate, orPredicate));
List<Employee> results = em.createQuery(cq).getResultList();
```

### Dynamic predicate building pattern

```java
public List<Employee> search(EmployeeSearchCriteria criteria) {
    CriteriaBuilder cb = em.getCriteriaBuilder();
    CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
    Root<Employee> emp = cq.from(Employee.class);

    List<Predicate> predicates = new ArrayList<>();

    if (criteria.getName() != null) {
        predicates.add(cb.like(cb.lower(emp.get("lastName")),
            "%" + criteria.getName().toLowerCase() + "%"));
    }
    if (criteria.getMinSalary() != null) {
        predicates.add(cb.greaterThanOrEqualTo(emp.get("salary"), criteria.getMinSalary()));
    }
    if (criteria.getDepartments() != null && !criteria.getDepartments().isEmpty()) {
        predicates.add(emp.get("department").get("name").in(criteria.getDepartments()));
    }

    cq.where(predicates.toArray(new Predicate[0]));
    return em.createQuery(cq).getResultList();
}
```

---

## Q103: How to do JOIN using Criteria API?

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// INNER JOIN
Join<Employee, Department> dept = emp.join("department");
cq.where(cb.equal(dept.get("name"), "Engineering"));

// LEFT JOIN
Join<Employee, Project> project = emp.join("projects", JoinType.LEFT);
cq.where(cb.equal(project.get("status"), "ACTIVE"));

// FETCH JOIN (to avoid N+1)
Fetch<Employee, Department> deptFetch = emp.fetch("department");
// Cannot add WHERE conditions on Fetch directly - use join if you need filtering

// FETCH JOIN with LEFT
emp.fetch("projects", JoinType.LEFT);
cq.select(emp).distinct(true);

// Multiple joins
Join<Employee, Department> deptJoin = emp.join("department");
Join<Employee, Address> addrJoin = emp.join("addresses", JoinType.LEFT);
cq.where(
    cb.and(
        cb.equal(deptJoin.get("name"), "IT"),
        cb.equal(addrJoin.get("city"), "London")
    )
);

// Nested join (join through a join)
Join<Employee, Department> d = emp.join("department");
Join<Department, Company> c = d.join("company");
cq.where(cb.equal(c.get("name"), "Acme Corp"));
```

```java
// Complete example: Employees in active projects in NYC departments
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

Join<Employee, Department> dept = emp.join("department");
Join<Employee, Project> proj = emp.join("projects");

cq.select(emp).distinct(true)
  .where(cb.and(
      cb.equal(dept.get("location"), "NYC"),
      cb.equal(proj.get("status"), ProjectStatus.ACTIVE)
  ));

List<Employee> results = em.createQuery(cq).getResultList();
```

---

## Q104: How to do sorting and pagination with Criteria API?

### Sorting

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// Single sort
cq.orderBy(cb.asc(emp.get("lastName")));

// Multiple sorts
cq.orderBy(
    cb.desc(emp.get("salary")),
    cb.asc(emp.get("lastName")),
    cb.asc(emp.get("firstName"))
);

// Dynamic sorting
List<Order> orders = new ArrayList<>();
if ("salary".equals(sortField)) {
    orders.add(sortDir.equals("ASC") ? cb.asc(emp.get("salary")) : cb.desc(emp.get("salary")));
}
orders.add(cb.asc(emp.get("id"))); // stable sort
cq.orderBy(orders);
```

### Pagination

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);
cq.select(emp).orderBy(cb.asc(emp.get("id")));

// Page 3 with 20 items per page
int pageNumber = 3;
int pageSize = 20;

TypedQuery<Employee> query = em.createQuery(cq);
query.setFirstResult((pageNumber - 1) * pageSize); // offset = 40
query.setMaxResults(pageSize);                      // limit = 20
List<Employee> page = query.getResultList();

// Get total count for pagination metadata
CriteriaQuery<Long> countQuery = cb.createQuery(Long.class);
Root<Employee> countRoot = countQuery.from(Employee.class);
countQuery.select(cb.count(countRoot));
// Apply same predicates as main query
Long totalCount = em.createQuery(countQuery).getSingleResult();
int totalPages = (int) Math.ceil((double) totalCount / pageSize);
```

### Reusable pagination utility

```java
public <T> PaginatedResult<T> paginate(CriteriaQuery<T> cq, Root<T> root, int page, int size) {
    CriteriaBuilder cb = em.getCriteriaBuilder();

    // Count query
    CriteriaQuery<Long> countCq = cb.createQuery(Long.class);
    Root<T> countRoot = countCq.from(root.getJavaType());
    countCq.select(cb.count(countRoot));
    if (cq.getRestriction() != null) {
        countCq.where(cq.getRestriction());
    }
    Long total = em.createQuery(countCq).getSingleResult();

    // Data query
    TypedQuery<T> query = em.createQuery(cq);
    query.setFirstResult(page * size);
    query.setMaxResults(size);
    List<T> data = query.getResultList();

    return new PaginatedResult<>(data, total, page, size);
}
```

---

## Q105: What is Metamodel API? How to use type-safe criteria queries?

The **Metamodel API** generates static metamodel classes that provide compile-time type safety for Criteria queries, eliminating string-based attribute references.

### Setup

Add the Hibernate JPA Metamodel Generator:

```xml
<dependency>
    <groupId>org.hibernate</groupId>
    <artifactId>hibernate-jpamodelgen</artifactId>
    <scope>provided</scope>
</dependency>
```

### Generated Metamodel class

For an entity `Employee`, a class `Employee_` is generated:

```java
// Auto-generated: Employee_.java
@StaticMetamodel(Employee.class)
public class Employee_ {
    public static volatile SingularAttribute<Employee, Long> id;
    public static volatile SingularAttribute<Employee, String> firstName;
    public static volatile SingularAttribute<Employee, String> lastName;
    public static volatile SingularAttribute<Employee, Double> salary;
    public static volatile SingularAttribute<Employee, Department> department;
    public static volatile SetAttribute<Employee, Project> projects;
}
```

### Usage - Type-safe queries

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// Type-safe: compile error if field doesn't exist or wrong type
cq.select(emp)
  .where(cb.and(
      cb.greaterThan(emp.get(Employee_.salary), 50000.0),
      cb.equal(emp.get(Employee_.department).get(Department_.name), "IT")
  ))
  .orderBy(cb.asc(emp.get(Employee_.lastName)));

// Type-safe join
Join<Employee, Department> dept = emp.join(Employee_.department);
cq.where(cb.equal(dept.get(Department_.location), "NYC"));
```

### Benefits

- **Compile-time safety** - Typos in field names caught at compile time
- **Refactoring support** - IDE can rename fields safely
- **Auto-complete** - IDE suggests available attributes
- **No runtime errors** from misspelled strings

---

## Q106: What is a Tuple query in Criteria API?

A **Tuple query** allows selecting multiple columns and accessing them in a type-safe way using aliases or indices, without creating a custom DTO.

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Tuple> cq = cb.createTupleQuery();
Root<Employee> emp = cq.from(Employee.class);

// Select multiple fields as a Tuple
cq.multiselect(
    emp.get("firstName").alias("first"),
    emp.get("lastName").alias("last"),
    emp.get("salary").alias("salary"),
    emp.get("department").get("name").alias("dept")
);

cq.where(cb.greaterThan(emp.get("salary"), 50000.0));

List<Tuple> results = em.createQuery(cq).getResultList();

for (Tuple tuple : results) {
    // Access by alias
    String firstName = tuple.get("first", String.class);
    String lastName = tuple.get("last", String.class);
    Double salary = tuple.get("salary", Double.class);
    String dept = tuple.get("dept", String.class);

    // Or by index
    String fn = tuple.get(0, String.class);
    String ln = tuple.get(1, String.class);
}
```

### When to use Tuple vs Object[] vs DTO

| Approach | Type Safety | Readability | Use Case |
|----------|------------|-------------|----------|
| `Object[]` | None | Poor | Quick ad-hoc queries |
| `Tuple` | Partial (at access time) | Good (aliases) | Multi-column selects without DTO |
| DTO projection | Full | Best | Reusable result types |

---

## Q107: How to use native SQL queries in JPA?

```java
// Simple native query returning entity
List<Employee> employees = em.createNativeQuery(
    "SELECT * FROM employees WHERE salary > ?1", Employee.class)
    .setParameter(1, 50000.0)
    .getResultList();

// Native query with named parameters (Hibernate extension)
List<Employee> employees = em.createNativeQuery(
    "SELECT * FROM employees WHERE department_id = :deptId", Employee.class)
    .setParameter("deptId", 5L)
    .getResultList();

// Native query returning scalar values
List<Object[]> results = em.createNativeQuery(
    "SELECT name, COUNT(*) as cnt FROM departments d " +
    "JOIN employees e ON e.dept_id = d.id " +
    "GROUP BY d.name HAVING COUNT(*) > 5")
    .getResultList();

// Using database-specific features
List<Object[]> results = em.createNativeQuery(
    "SELECT e.*, RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rank " +
    "FROM employees e")
    .getResultList();

// Native query with UPDATE
int updated = em.createNativeQuery(
    "UPDATE employees SET salary = salary * 1.1 WHERE dept_id = :deptId")
    .setParameter("deptId", 3L)
    .executeUpdate();
```

### Spring Data JPA approach

```java
@Repository
public interface EmployeeRepository extends JpaRepository<Employee, Long> {

    @Query(value = "SELECT * FROM employees WHERE salary > :salary", nativeQuery = true)
    List<Employee> findHighEarners(@Param("salary") double salary);

    @Query(value = "SELECT * FROM employees ORDER BY salary DESC LIMIT :limit", nativeQuery = true)
    List<Employee> findTopEarners(@Param("limit") int limit);

    @Modifying
    @Query(value = "UPDATE employees SET active = false WHERE last_login < :date", nativeQuery = true)
    int deactivateInactiveUsers(@Param("date") LocalDate date);
}
```

---

## Q108: What is @SqlResultSetMapping?

`@SqlResultSetMapping` maps native SQL query results to entities, constructors, or scalar columns.

```java
@Entity
@SqlResultSetMappings({
    // Map to entity
    @SqlResultSetMapping(
        name = "EmployeeMapping",
        entities = @EntityResult(
            entityClass = Employee.class,
            fields = {
                @FieldResult(name = "id", column = "emp_id"),
                @FieldResult(name = "firstName", column = "first_name"),
                @FieldResult(name = "lastName", column = "last_name"),
                @FieldResult(name = "salary", column = "emp_salary")
            }
        )
    ),
    // Map to multiple entities
    @SqlResultSetMapping(
        name = "EmployeeWithDeptMapping",
        entities = {
            @EntityResult(entityClass = Employee.class),
            @EntityResult(entityClass = Department.class)
        }
    ),
    // Map to constructor (DTO)
    @SqlResultSetMapping(
        name = "EmployeeSummaryMapping",
        classes = @ConstructorResult(
            targetClass = EmployeeSummaryDTO.class,
            columns = {
                @ColumnResult(name = "full_name", type = String.class),
                @ColumnResult(name = "dept_name", type = String.class),
                @ColumnResult(name = "salary", type = Double.class)
            }
        )
    ),
    // Map to scalar columns
    @SqlResultSetMapping(
        name = "StatsMapping",
        columns = {
            @ColumnResult(name = "department", type = String.class),
            @ColumnResult(name = "total", type = Long.class),
            @ColumnResult(name = "average", type = Double.class)
        }
    )
})
public class Employee { /* ... */ }
```

### Usage

```java
// Using constructor result mapping
List<EmployeeSummaryDTO> summaries = em.createNativeQuery(
    "SELECT CONCAT(e.first_name, ' ', e.last_name) as full_name, " +
    "d.name as dept_name, e.salary " +
    "FROM employees e JOIN departments d ON e.dept_id = d.id",
    "EmployeeSummaryMapping")
    .getResultList();
```

---

## Q109: How to use DTO projections in JPQL (constructor expression)?

The **constructor expression** (`SELECT NEW`) creates DTO instances directly from JPQL results.

### DTO class

```java
package com.example.dto;

public class EmployeeDTO {
    private String fullName;
    private String departmentName;
    private Double salary;

    // Constructor must match the SELECT NEW parameters exactly
    public EmployeeDTO(String fullName, String departmentName, Double salary) {
        this.fullName = fullName;
        this.departmentName = departmentName;
        this.salary = salary;
    }

    // Getters
}
```

### JPQL with constructor expression

```java
// Must use fully qualified class name
TypedQuery<EmployeeDTO> query = em.createQuery(
    "SELECT NEW com.example.dto.EmployeeDTO(" +
    "  CONCAT(e.firstName, ' ', e.lastName), " +
    "  e.department.name, " +
    "  e.salary) " +
    "FROM Employee e WHERE e.active = true " +
    "ORDER BY e.salary DESC",
    EmployeeDTO.class);

List<EmployeeDTO> dtos = query.getResultList();
```

### Spring Data JPA - Interface-based projection (alternative)

```java
public interface EmployeeProjection {
    String getFirstName();
    String getLastName();
    Double getSalary();

    @Value("#{target.firstName + ' ' + target.lastName}")
    String getFullName();
}

@Repository
public interface EmployeeRepository extends JpaRepository<Employee, Long> {
    List<EmployeeProjection> findByDepartmentName(String deptName);

    // Class-based projection
    @Query("SELECT NEW com.example.dto.EmployeeDTO(e.firstName, e.lastName, e.salary) " +
           "FROM Employee e WHERE e.department.name = :dept")
    List<EmployeeDTO> findDTOByDepartment(@Param("dept") String dept);
}
```

### Benefits of DTO projections

- Only fetches needed columns (performance)
- No managed entity overhead
- No dirty checking
- Read-only by design
- Clear API contract

---

## Q110: What is the difference between TypedQuery and Query?

```java
// Query - untyped, returns Object or Object[]
Query query = em.createQuery("SELECT e FROM Employee e");
List results = query.getResultList(); // unchecked, raw type
Employee emp = (Employee) results.get(0); // manual cast needed

// TypedQuery<T> - type-safe, returns T
TypedQuery<Employee> typedQuery = em.createQuery(
    "SELECT e FROM Employee e", Employee.class);
List<Employee> results = typedQuery.getResultList(); // type-safe
Employee emp = results.get(0); // no cast needed
```

| Aspect | Query | TypedQuery\<T\> |
|--------|-------|-----------------|
| Return type | Raw `Object`/`List` | Typed `T`/`List<T>` |
| Type safety | No (requires casting) | Yes |
| Compile-time check | No | Yes |
| Use case | Native queries, dynamic result types | JPQL with known return type |

### When you must use Query

```java
// Native queries without result class (before JPA 2.1)
Query q = em.createNativeQuery("SELECT id, name FROM departments");

// Mixed scalar results
Query q = em.createQuery("SELECT e.name, e.salary FROM Employee e");
List<Object[]> results = q.getResultList();
```

**Best practice**: Always prefer `TypedQuery` when the result type is known.

---

## Q111: How to handle NULL values in JPQL?

```java
// IS NULL
String jpql = "SELECT e FROM Employee e WHERE e.manager IS NULL";

// IS NOT NULL
String jpql = "SELECT e FROM Employee e WHERE e.email IS NOT NULL";

// COALESCE - returns first non-null value
String jpql = "SELECT e.firstName, COALESCE(e.nickname, e.firstName) FROM Employee e";

// NULLIF - returns null if two expressions are equal
String jpql = "SELECT e.firstName, NULLIF(e.bonus, 0) FROM Employee e";
// Returns null if bonus is 0, otherwise returns bonus

// CASE with NULL handling
String jpql = "SELECT e.firstName, " +
    "CASE WHEN e.manager IS NULL THEN 'Top Level' ELSE e.manager.lastName END " +
    "FROM Employee e";

// NULL in comparisons - won't match
// This does NOT return employees with null department:
String jpql = "SELECT e FROM Employee e WHERE e.department.name != 'IT'";
// Must explicitly include: OR e.department IS NULL

// Correct way to include nulls
String jpql = "SELECT e FROM Employee e WHERE e.department.name != 'IT' OR e.department IS NULL";

// ORDER BY with nulls (Hibernate-specific)
String jpql = "SELECT e FROM Employee e ORDER BY e.manager.lastName ASC NULLS LAST";
```

### Criteria API null handling

```java
CriteriaBuilder cb = em.getCriteriaBuilder();
CriteriaQuery<Employee> cq = cb.createQuery(Employee.class);
Root<Employee> emp = cq.from(Employee.class);

// IS NULL
Predicate isNull = cb.isNull(emp.get("manager"));

// IS NOT NULL
Predicate isNotNull = cb.isNotNull(emp.get("email"));

// COALESCE
cq.select(emp).orderBy(
    cb.asc(cb.coalesce(emp.get("nickname"), emp.get("firstName")))
);
```

---

## Q112: What are bulk update and delete operations in JPQL?

Bulk operations execute directly in the database, **bypassing the persistence context** (entities in memory are not updated).

### Bulk UPDATE

```java
// Bulk update
int updatedCount = em.createQuery(
    "UPDATE Employee e SET e.salary = e.salary * 1.1 WHERE e.department.name = :dept")
    .setParameter("dept", "Engineering")
    .executeUpdate();

// Multiple fields
int updated = em.createQuery(
    "UPDATE Employee e SET e.status = :newStatus, e.lastModified = :now " +
    "WHERE e.status = :oldStatus AND e.lastLogin < :cutoff")
    .setParameter("newStatus", Status.INACTIVE)
    .setParameter("now", LocalDateTime.now())
    .setParameter("oldStatus", Status.ACTIVE)
    .setParameter("cutoff", LocalDateTime.now().minusMonths(6))
    .executeUpdate();
```

### Bulk DELETE

```java
int deletedCount = em.createQuery(
    "DELETE FROM Employee e WHERE e.status = :status AND e.terminationDate < :date")
    .setParameter("status", Status.TERMINATED)
    .setParameter("date", LocalDate.now().minusYears(1))
    .executeUpdate();
```

### Important: Persistence context is stale after bulk operations

```java
@Transactional
public void giveRaise(String dept) {
    // Bulk update bypasses persistence context
    em.createQuery("UPDATE Employee e SET e.salary = e.salary * 1.1 WHERE e.department.name = :dept")
        .setParameter("dept", dept)
        .executeUpdate();

    // CRITICAL: Clear the persistence context to avoid stale data
    em.flush();
    em.clear();

    // Now queries will reflect the update
    List<Employee> updated = em.createQuery(
        "SELECT e FROM Employee e WHERE e.department.name = :dept", Employee.class)
        .setParameter("dept", dept)
        .getResultList();
}
```

### Spring Data JPA

```java
@Modifying(clearAutomatically = true) // auto-clears persistence context
@Query("UPDATE Employee e SET e.active = false WHERE e.lastLogin < :date")
int deactivateInactive(@Param("date") LocalDateTime date);
```

---

## Q113: What is QueryHint and how to use it?

**Query hints** pass provider-specific instructions to optimize query execution.

```java
// JPA standard way
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e WHERE e.department.name = :dept", Employee.class)
    .setParameter("dept", "IT")
    .setHint("org.hibernate.cacheable", true)
    .setHint("org.hibernate.fetchSize", 50)
    .setHint("org.hibernate.readOnly", true)
    .setHint("org.hibernate.timeout", 10)
    .setHint("javax.persistence.query.timeout", 5000); // milliseconds (JPA standard)
```

### Common Hibernate query hints

| Hint | Description |
|------|-------------|
| `org.hibernate.cacheable` | Enable second-level query cache |
| `org.hibernate.cacheRegion` | Specify cache region name |
| `org.hibernate.readOnly` | Mark results as read-only (no dirty checking) |
| `org.hibernate.fetchSize` | JDBC fetch size |
| `org.hibernate.timeout` | Query timeout in seconds |
| `org.hibernate.comment` | Add SQL comment for debugging |
| `org.hibernate.flushMode` | Override flush mode for this query |
| `javax.persistence.lock.timeout` | Lock timeout in ms |

### With @NamedQuery

```java
@NamedQuery(
    name = "Employee.findAll",
    query = "SELECT e FROM Employee e",
    hints = {
        @QueryHint(name = "org.hibernate.cacheable", value = "true"),
        @QueryHint(name = "org.hibernate.readOnly", value = "true")
    }
)
```

### Spring Data JPA

```java
@QueryHints({
    @QueryHint(name = "org.hibernate.cacheable", value = "true"),
    @QueryHint(name = "org.hibernate.readOnly", value = "true")
})
@Query("SELECT e FROM Employee e WHERE e.active = true")
List<Employee> findActiveEmployees();
```

---

## Q114: How to use pagination with JPQL (setFirstResult, setMaxResults)?

```java
// Basic pagination
int pageNumber = 2; // 0-indexed
int pageSize = 25;

TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e ORDER BY e.id", Employee.class);
query.setFirstResult(pageNumber * pageSize); // offset: skip first 50
query.setMaxResults(pageSize);                // limit: return 25
List<Employee> page = query.getResultList();

// Get total count
Long totalCount = em.createQuery(
    "SELECT COUNT(e) FROM Employee e", Long.class)
    .getSingleResult();
```

### Pagination utility

```java
public class Page<T> {
    private List<T> content;
    private int pageNumber;
    private int pageSize;
    private long totalElements;
    private int totalPages;

    public Page(List<T> content, int pageNumber, int pageSize, long totalElements) {
        this.content = content;
        this.pageNumber = pageNumber;
        this.pageSize = pageSize;
        this.totalElements = totalElements;
        this.totalPages = (int) Math.ceil((double) totalElements / pageSize);
    }

    public boolean hasNext() { return pageNumber < totalPages - 1; }
    public boolean hasPrevious() { return pageNumber > 0; }
}
```

### Important: Always include ORDER BY for consistent pagination

```java
// BAD - non-deterministic ordering
query = em.createQuery("SELECT e FROM Employee e", Employee.class);
query.setFirstResult(20).setMaxResults(10); // results may vary between calls

// GOOD - deterministic ordering
query = em.createQuery("SELECT e FROM Employee e ORDER BY e.id ASC", Employee.class);
query.setFirstResult(20).setMaxResults(10);
```

### Keyset pagination (better performance for large offsets)

```java
// Instead of OFFSET (slow for large values), use keyset/cursor-based pagination
TypedQuery<Employee> query = em.createQuery(
    "SELECT e FROM Employee e WHERE e.id > :lastId ORDER BY e.id ASC", Employee.class)
    .setParameter("lastId", lastSeenId)
    .setMaxResults(pageSize);
```

---

## Q115: What is FlushModeType and how does it affect queries?

**FlushModeType** controls when Hibernate synchronizes (flushes) pending changes from the persistence context to the database before executing a query.

### Two modes

| Mode | Behavior |
|------|----------|
| `AUTO` (default) | Flush before queries that might be affected by pending changes |
| `COMMIT` | Only flush on transaction commit; queries may return stale data |

### How it affects queries

```java
Employee emp = em.find(Employee.class, 1L);
emp.setSalary(100000.0); // Change in persistence context, not yet in DB

// AUTO mode (default): Hibernate flushes before this query
// so the updated salary is visible
List<Employee> highEarners = em.createQuery(
    "SELECT e FROM Employee e WHERE e.salary > 90000", Employee.class)
    .getResultList(); // includes emp with new salary

// COMMIT mode: No flush before query, database still has old salary
List<Employee> highEarners = em.createQuery(
    "SELECT e FROM Employee e WHERE e.salary > 90000", Employee.class)
    .setFlushMode(FlushModeType.COMMIT)
    .getResultList(); // may NOT include emp
```

### Setting flush mode

```java
// Per-query
query.setFlushMode(FlushModeType.COMMIT);

// Per EntityManager (session)
em.setFlushMode(FlushModeType.COMMIT);

// Per @NamedQuery
@NamedQuery(
    name = "Employee.reporting",
    query = "SELECT e FROM Employee e",
    hints = @QueryHint(name = "org.hibernate.flushMode", value = "COMMIT")
)
```

### When to use COMMIT mode

- **Read-only reporting queries** where you know there are no pending changes that matter
- **Performance optimization** to avoid unnecessary flushes
- Queries inside loops where flushing each time would be expensive

### Spring Data JPA

```java
@QueryHints(@QueryHint(name = "org.hibernate.flushMode", value = "COMMIT"))
@Query("SELECT e FROM Employee e WHERE e.department.name = :dept")
List<Employee> findByDeptReadOnly(@Param("dept") String dept);
```

**Warning**: Using `COMMIT` mode can lead to inconsistent reads if you have unflushed modifications in the persistence context that affect the query results.
