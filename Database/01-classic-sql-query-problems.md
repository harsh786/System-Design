# Classic SQL Query Interview Problems (Problems 1-25)

## Staff Architect Level - Database Interview Questions

---

## Problem 1: Second Highest Salary

**Difficulty:** Medium | **Frequency:** Very High (Asked at Google, Amazon, Meta, Microsoft)

**Problem:** Given an `Employee` table, find the second highest salary. If there is no second highest salary, return `null`.

```sql
CREATE TABLE Employee (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    salary INT
);
```

**Solution 1: Using Subquery**
```sql
SELECT MAX(salary) AS SecondHighestSalary
FROM Employee
WHERE salary < (SELECT MAX(salary) FROM Employee);
```

**Solution 2: Using LIMIT/OFFSET**
```sql
SELECT DISTINCT salary AS SecondHighestSalary
FROM Employee
ORDER BY salary DESC
LIMIT 1 OFFSET 1;
```

**Solution 3: Using DENSE_RANK (handles ties correctly)**
```sql
SELECT salary AS SecondHighestSalary
FROM (
    SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS rnk
    FROM Employee
) ranked
WHERE rnk = 2
LIMIT 1;
```

**Why DENSE_RANK over ROW_NUMBER?**
- `ROW_NUMBER()` assigns unique numbers even for ties — may skip valid salaries
- `DENSE_RANK()` handles duplicates correctly — two people with same highest salary still let you find actual 2nd value
- `RANK()` would skip ranks after ties (1,1,3) vs DENSE_RANK (1,1,2)

**Edge Cases:**
- Table is empty → return NULL
- All employees have same salary → return NULL
- Only one distinct salary → return NULL

**Follow-up:** How would you handle this at scale with 100M rows?
- Create an index on `salary DESC`
- The `LIMIT/OFFSET` approach with index becomes O(log n)

---

## Problem 2: Nth Highest Salary

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Write a function to get the Nth highest salary.

```sql
CREATE FUNCTION getNthHighestSalary(N INT) RETURNS INT
BEGIN
    DECLARE M INT;
    SET M = N - 1;
    RETURN (
        SELECT DISTINCT salary
        FROM Employee
        ORDER BY salary DESC
        LIMIT 1 OFFSET M
    );
END;
```

**Solution using DENSE_RANK:**
```sql
SELECT salary AS NthHighestSalary
FROM (
    SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS rnk
    FROM Employee
) ranked
WHERE rnk = N
LIMIT 1;
```

**Architect Insight:** At scale, consider materializing a salary_ranks table if this query is frequent. Pre-computing ranks avoids expensive window functions on hot paths.

---

## Problem 3: Find Duplicate Emails

**Difficulty:** Easy | **Frequency:** Very High

**Problem:** Find all duplicate emails in a table.

```sql
CREATE TABLE Person (
    id INT PRIMARY KEY,
    email VARCHAR(255)
);
```

**Solution 1: GROUP BY + HAVING**
```sql
SELECT email
FROM Person
GROUP BY email
HAVING COUNT(*) > 1;
```

**Solution 2: Self-Join**
```sql
SELECT DISTINCT p1.email
FROM Person p1
JOIN Person p2 ON p1.email = p2.email AND p1.id != p2.id;
```

**Solution 3: Using Window Function**
```sql
SELECT DISTINCT email
FROM (
    SELECT email, COUNT(*) OVER (PARTITION BY email) AS cnt
    FROM Person
) t
WHERE cnt > 1;
```

**Architect Discussion:**
- GROUP BY approach is most efficient (single pass with hash aggregation)
- Self-join creates a cartesian product within each email group — O(n²) in worst case
- In production, prevent duplicates with UNIQUE constraint + handle at application level
- For deduplication at scale: use `ROW_NUMBER()` to identify and delete extras

---

## Problem 4: Delete Duplicate Emails (Keep Lowest ID)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Delete all duplicate emails, keeping only the one with the smallest id.

**Solution 1: DELETE with Self-Join**
```sql
DELETE p1
FROM Person p1
JOIN Person p2
ON p1.email = p2.email AND p1.id > p2.id;
```

**Solution 2: Using CTE + ROW_NUMBER**
```sql
WITH ranked AS (
    SELECT id, email, ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) AS rn
    FROM Person
)
DELETE FROM Person WHERE id IN (
    SELECT id FROM ranked WHERE rn > 1
);
```

**Architect Considerations:**
- For tables with billions of rows, batch deletions to avoid lock contention
- Use `DELETE ... LIMIT 10000` in a loop with transactions
- Consider soft-delete (add `is_deleted` flag) for audit trail
- In distributed systems, deduplication requires idempotency tokens

---

## Problem 5: Customers Who Never Order

**Difficulty:** Easy | **Frequency:** Very High

**Problem:** Find customers who never placed an order.

```sql
CREATE TABLE Customers (id INT, name VARCHAR(255));
CREATE TABLE Orders (id INT, customerId INT);
```

**Solution 1: LEFT JOIN + NULL check**
```sql
SELECT c.name AS Customers
FROM Customers c
LEFT JOIN Orders o ON c.id = o.customerId
WHERE o.id IS NULL;
```

**Solution 2: NOT EXISTS (often faster)**
```sql
SELECT name AS Customers
FROM Customers c
WHERE NOT EXISTS (
    SELECT 1 FROM Orders o WHERE o.customerId = c.id
);
```

**Solution 3: NOT IN**
```sql
SELECT name AS Customers
FROM Customers
WHERE id NOT IN (SELECT customerId FROM Orders WHERE customerId IS NOT NULL);
```

**Performance Comparison (Architect Level):**
| Approach | Index Needed | Performance | NULL Safety |
|----------|-------------|-------------|-------------|
| LEFT JOIN + NULL | Orders(customerId) | Good | Safe |
| NOT EXISTS | Orders(customerId) | Best (short-circuits) | Safe |
| NOT IN | Orders(customerId) | Risky with NULLs | Dangerous if NULLs exist |

**Critical Warning:** `NOT IN` returns empty result if ANY value in subquery is NULL. Always prefer `NOT EXISTS`.

---

## Problem 6: Rising Temperature (Consecutive Day Comparison)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Find all dates where temperature was higher than the previous day.

```sql
CREATE TABLE Weather (
    id INT PRIMARY KEY,
    recordDate DATE,
    temperature INT
);
```

**Solution 1: Self-Join with DATEDIFF**
```sql
SELECT w1.id
FROM Weather w1
JOIN Weather w2
ON DATEDIFF(w1.recordDate, w2.recordDate) = 1
WHERE w1.temperature > w2.temperature;
```

**Solution 2: Using LAG Window Function**
```sql
SELECT id
FROM (
    SELECT id, temperature, recordDate,
           LAG(temperature) OVER (ORDER BY recordDate) AS prev_temp,
           LAG(recordDate) OVER (ORDER BY recordDate) AS prev_date
    FROM Weather
) t
WHERE temperature > prev_temp
  AND DATEDIFF(recordDate, prev_date) = 1;
```

**Why check DATEDIFF?** Dates may not be consecutive (gaps in data). Without the check, you'd compare against non-adjacent days.

**Architect Insight:** For time-series data at scale, consider:
- TimescaleDB (PostgreSQL extension) with hypertables
- ClickHouse for OLAP queries on time-series
- Partition by date ranges for efficient pruning

---

## Problem 7: Department Top Three Salaries

**Difficulty:** Hard | **Frequency:** Very High (FAANG favorite)

**Problem:** Find employees who earn top 3 salaries in each department.

```sql
CREATE TABLE Employee (id INT, name VARCHAR, salary INT, departmentId INT);
CREATE TABLE Department (id INT, name VARCHAR);
```

**Solution:**
```sql
SELECT d.name AS Department, e.name AS Employee, e.salary AS Salary
FROM (
    SELECT name, salary, departmentId,
           DENSE_RANK() OVER (PARTITION BY departmentId ORDER BY salary DESC) AS rnk
    FROM Employee
) e
JOIN Department d ON e.departmentId = d.id
WHERE e.rnk <= 3;
```

**Why DENSE_RANK?**
- If 3 people tie for #1, all should be included
- RANK would give 1,1,1,4 — missing rank 2 and 3
- DENSE_RANK gives 1,1,1,2 — correctly identifies next salary tier

**Architect Discussion:**
- Index: `Employee(departmentId, salary DESC)` for partition-aware scanning
- For real-time dashboards, materialize this with triggers or CDC
- Consider approximate top-K algorithms for very large datasets

---

## Problem 8: Consecutive Numbers (Find 3+ Consecutive Same Values)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Find numbers that appear at least three times consecutively.

```sql
CREATE TABLE Logs (id INT PRIMARY KEY AUTO_INCREMENT, num INT);
```

**Solution 1: Self-Join**
```sql
SELECT DISTINCT l1.num AS ConsecutiveNums
FROM Logs l1
JOIN Logs l2 ON l1.id = l2.id - 1
JOIN Logs l3 ON l2.id = l3.id - 1
WHERE l1.num = l2.num AND l2.num = l3.num;
```

**Solution 2: Window Function (Gaps and Islands)**
```sql
WITH grouped AS (
    SELECT num, id,
           id - ROW_NUMBER() OVER (PARTITION BY num ORDER BY id) AS grp
    FROM Logs
)
SELECT DISTINCT num AS ConsecutiveNums
FROM grouped
GROUP BY num, grp
HAVING COUNT(*) >= 3;
```

**Gaps and Islands Technique Explained:**
- For consecutive rows with same value, `id - ROW_NUMBER()` produces same value
- This creates a "group identifier" for consecutive sequences
- Fundamental technique for detecting streaks, sessions, and patterns

---

## Problem 9: Rank Scores (Dense Ranking Without Gaps)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Rank scores in descending order. Ties get same rank, no gaps.

```sql
SELECT score,
       DENSE_RANK() OVER (ORDER BY score DESC) AS 'rank'
FROM Scores
ORDER BY score DESC;
```

**Without Window Functions (for older MySQL):**
```sql
SELECT s.score,
       (SELECT COUNT(DISTINCT s2.score) 
        FROM Scores s2 
        WHERE s2.score >= s.score) AS 'rank'
FROM Scores s
ORDER BY s.score DESC;
```

---

## Problem 10: Exchange Seats (Swap Adjacent Rows)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Swap every two consecutive students' seats. If odd number of students, last one stays.

```sql
SELECT 
    CASE 
        WHEN id % 2 = 1 AND id = (SELECT MAX(id) FROM Seat) THEN id
        WHEN id % 2 = 1 THEN id + 1
        ELSE id - 1
    END AS id,
    student
FROM Seat
ORDER BY id;
```

**Using Window Functions:**
```sql
SELECT 
    ROW_NUMBER() OVER (ORDER BY 
        CASE 
            WHEN id % 2 = 0 THEN id - 1
            ELSE id + 1
        END,
        id
    ) AS id,
    student
FROM Seat;
```

---

## Problem 11: Employees Earning More Than Their Managers

**Difficulty:** Easy | **Frequency:** Very High

**Problem:** Find employees who earn more than their managers.

```sql
CREATE TABLE Employee (id INT, name VARCHAR, salary INT, managerId INT);
```

**Solution:**
```sql
SELECT e.name AS Employee
FROM Employee e
JOIN Employee m ON e.managerId = m.id
WHERE e.salary > m.salary;
```

**Architect Discussion:**
- Self-join pattern is fundamental for hierarchical data
- For deep hierarchies (org charts), consider:
  - Adjacency list (simple, slow for deep queries)
  - Nested sets (fast reads, slow writes)
  - Materialized path (good balance)
  - Closure table (best for complex hierarchy queries)

---

## Problem 12: Trips and Users (Complex Multi-Join with Filters)

**Difficulty:** Hard | **Frequency:** High (Uber, Lyft interviews)

**Problem:** Find cancellation rate for unbanned users between specific dates.

```sql
CREATE TABLE Trips (id INT, client_id INT, driver_id INT, status ENUM('completed','cancelled_by_driver','cancelled_by_client'), request_at DATE);
CREATE TABLE Users (users_id INT, banned VARCHAR(3), role ENUM('client','driver'));
```

**Solution:**
```sql
SELECT t.request_at AS Day,
       ROUND(
           SUM(CASE WHEN t.status != 'completed' THEN 1 ELSE 0 END) / COUNT(*), 
           2
       ) AS 'Cancellation Rate'
FROM Trips t
JOIN Users u1 ON t.client_id = u1.users_id AND u1.banned = 'No'
JOIN Users u2 ON t.driver_id = u2.users_id AND u2.banned = 'No'
WHERE t.request_at BETWEEN '2013-10-01' AND '2013-10-03'
GROUP BY t.request_at;
```

**Architect Insight:**
- This requires filtering on BOTH client and driver being unbanned
- The double-join pattern is common in marketplace systems
- At scale, denormalize `banned` status into Trips table (event sourcing)
- Consider pre-aggregated metrics tables for dashboard queries

---

## Problem 13: Human Traffic of Stadium (3+ Consecutive Rows with Threshold)

**Difficulty:** Hard | **Frequency:** High

**Problem:** Find rows where people >= 100 for 3 or more consecutive days.

```sql
CREATE TABLE Stadium (id INT, visit_date DATE, people INT);
```

**Solution using Gaps and Islands:**
```sql
WITH filtered AS (
    SELECT *, id - ROW_NUMBER() OVER (ORDER BY id) AS grp
    FROM Stadium
    WHERE people >= 100
),
groups AS (
    SELECT grp, COUNT(*) AS cnt
    FROM filtered
    GROUP BY grp
    HAVING COUNT(*) >= 3
)
SELECT f.id, f.visit_date, f.people
FROM filtered f
JOIN groups g ON f.grp = g.grp
ORDER BY f.id;
```

---

## Problem 14: Median Employee Salary

**Difficulty:** Hard | **Frequency:** High

**Problem:** Find median salary for each company.

**Solution:**
```sql
WITH ranked AS (
    SELECT id, company, salary,
           ROW_NUMBER() OVER (PARTITION BY company ORDER BY salary, id) AS rn,
           COUNT(*) OVER (PARTITION BY company) AS cnt
    FROM Employee
)
SELECT id, company, salary
FROM ranked
WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0));
```

**Why Median is Tricky in SQL:**
- No built-in MEDIAN function in most databases
- Must handle both odd (single middle) and even (average of two middle) cases
- PostgreSQL has `PERCENTILE_CONT(0.5)` — use it when available
- For very large datasets, consider approximate percentiles (t-digest, HyperLogLog)

---

## Problem 15: Department Highest Salary

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Find employees with the highest salary in each department.

```sql
SELECT d.name AS Department, e.name AS Employee, e.salary AS Salary
FROM Employee e
JOIN Department d ON e.departmentId = d.id
WHERE (e.departmentId, e.salary) IN (
    SELECT departmentId, MAX(salary)
    FROM Employee
    GROUP BY departmentId
);
```

**Alternative with Window Function:**
```sql
WITH ranked AS (
    SELECT e.name AS Employee, e.salary, e.departmentId,
           RANK() OVER (PARTITION BY departmentId ORDER BY salary DESC) AS rnk
    FROM Employee e
)
SELECT d.name AS Department, r.Employee, r.salary AS Salary
FROM ranked r
JOIN Department d ON r.departmentId = d.id
WHERE r.rnk = 1;
```

---

## Problem 16: Tree Node Classification

**Difficulty:** Medium | **Frequency:** High

**Problem:** Classify each node as 'Root', 'Inner', or 'Leaf'.

```sql
CREATE TABLE Tree (id INT, p_id INT);
```

**Solution:**
```sql
SELECT id,
    CASE
        WHEN p_id IS NULL THEN 'Root'
        WHEN id IN (SELECT DISTINCT p_id FROM Tree WHERE p_id IS NOT NULL) THEN 'Inner'
        ELSE 'Leaf'
    END AS type
FROM Tree;
```

**Architect Discussion:** This is essentially graph classification in SQL. For complex graph queries:
- PostgreSQL: Recursive CTEs
- Neo4j: Purpose-built graph DB
- Amazon Neptune / Azure Cosmos DB Gremlin API for cloud-native graph

---

## Problem 17: Consecutive Available Seats (Find Adjacent Free Seats)

**Difficulty:** Medium | **Frequency:** High (Movie booking, Airlines)

**Problem:** Find all consecutive available seats.

```sql
CREATE TABLE Cinema (seat_id INT PRIMARY KEY, free BOOLEAN);
```

**Solution:**
```sql
SELECT DISTINCT c1.seat_id
FROM Cinema c1
JOIN Cinema c2 ON ABS(c1.seat_id - c2.seat_id) = 1
WHERE c1.free = 1 AND c2.free = 1
ORDER BY c1.seat_id;
```

**Using Window Functions:**
```sql
WITH consecutive AS (
    SELECT seat_id, free,
           LAG(free) OVER (ORDER BY seat_id) AS prev_free,
           LEAD(free) OVER (ORDER BY seat_id) AS next_free
    FROM Cinema
)
SELECT seat_id
FROM consecutive
WHERE free = 1 AND (prev_free = 1 OR next_free = 1)
ORDER BY seat_id;
```

---

## Problem 18: Friend Requests - Who Has Most Friends

**Difficulty:** Medium | **Frequency:** High (Social network design)

**Problem:** Find the person with most friends (accepted requests count both directions).

```sql
CREATE TABLE RequestAccepted (requester_id INT, accepter_id INT);
```

**Solution:**
```sql
SELECT id, COUNT(*) AS num
FROM (
    SELECT requester_id AS id FROM RequestAccepted
    UNION ALL
    SELECT accepter_id AS id FROM RequestAccepted
) all_friends
GROUP BY id
ORDER BY num DESC
LIMIT 1;
```

**Architect Insight:**
- Bidirectional relationships in SQL require UNION of both directions
- At Facebook/Meta scale, this is stored in TAO (graph-aware cache)
- Consider storing both directions explicitly for read performance
- Use graph databases for social network traversals (friends of friends)

---

## Problem 19: Sales Person Who Never Sold to Company "RED"

**Difficulty:** Medium | **Frequency:** High

**Problem:** Find salespeople who never had orders with company "RED".

```sql
SELECT s.name
FROM SalesPerson s
WHERE s.sales_id NOT IN (
    SELECT o.sales_id
    FROM Orders o
    JOIN Company c ON o.com_id = c.com_id
    WHERE c.name = 'RED'
);
```

**Safer version with NOT EXISTS:**
```sql
SELECT s.name
FROM SalesPerson s
WHERE NOT EXISTS (
    SELECT 1
    FROM Orders o
    JOIN Company c ON o.com_id = c.com_id
    WHERE o.sales_id = s.sales_id AND c.name = 'RED'
);
```

---

## Problem 20: Game Play Analysis - First Login Date

**Difficulty:** Easy-Medium | **Frequency:** Very High (Gaming companies)

**Problem:** Find first login date for each player.

```sql
CREATE TABLE Activity (player_id INT, device_id INT, event_date DATE, games_played INT);
```

**Solution:**
```sql
SELECT player_id, MIN(event_date) AS first_login
FROM Activity
GROUP BY player_id;
```

**Follow-up: Players who logged in on consecutive days after first login:**
```sql
WITH first_login AS (
    SELECT player_id, MIN(event_date) AS first_date
    FROM Activity
    GROUP BY player_id
)
SELECT ROUND(
    COUNT(DISTINCT a.player_id) / (SELECT COUNT(DISTINCT player_id) FROM Activity), 
    2
) AS fraction
FROM Activity a
JOIN first_login f ON a.player_id = f.player_id
WHERE a.event_date = DATE_ADD(f.first_date, INTERVAL 1 DAY);
```

---

## Problem 21: Running Total / Cumulative Sum

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Calculate running total of sales per customer ordered by date.

```sql
SELECT customer_id, order_date, amount,
       SUM(amount) OVER (
           PARTITION BY customer_id 
           ORDER BY order_date 
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_total
FROM Orders
ORDER BY customer_id, order_date;
```

**Frame Specification Deep Dive:**
```
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW  -- Default for ORDER BY
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW          -- 3-row moving average
ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING   -- Reverse running total
RANGE BETWEEN INTERVAL 7 DAY PRECEDING AND CURRENT ROW  -- 7-day window
```

**ROWS vs RANGE:**
- ROWS: Physical rows (exact count)
- RANGE: Logical value range (handles ties differently)
- GROUPS: Groups of peer rows (PostgreSQL 11+)

---

## Problem 22: Pivot Table - Monthly Sales Report

**Difficulty:** Medium | **Frequency:** High

**Problem:** Transform rows to columns showing monthly sales.

**Solution (MySQL/SQL Server):**
```sql
SELECT product,
    SUM(CASE WHEN MONTH(sale_date) = 1 THEN amount ELSE 0 END) AS Jan,
    SUM(CASE WHEN MONTH(sale_date) = 2 THEN amount ELSE 0 END) AS Feb,
    SUM(CASE WHEN MONTH(sale_date) = 3 THEN amount ELSE 0 END) AS Mar,
    -- ... remaining months
    SUM(CASE WHEN MONTH(sale_date) = 12 THEN amount ELSE 0 END) AS Dec
FROM Sales
GROUP BY product;
```

**SQL Server PIVOT:**
```sql
SELECT product, [Jan], [Feb], [Mar]
FROM (
    SELECT product, FORMAT(sale_date, 'MMM') AS month_name, amount
    FROM Sales
) src
PIVOT (
    SUM(amount) FOR month_name IN ([Jan], [Feb], [Mar])
) pvt;
```

**Architect Discussion:**
- Static pivots require knowing columns at query time
- Dynamic pivots need dynamic SQL (security concern: SQL injection)
- For analytics, consider columnar stores (ClickHouse, Redshift) or OLAP cubes
- In application layer, pivot in code (pandas, Spark) for flexibility

---

## Problem 23: Year-over-Year Growth

**Difficulty:** Medium | **Frequency:** Very High (Finance, Analytics)

**Problem:** Calculate YoY revenue growth percentage.

```sql
WITH yearly AS (
    SELECT YEAR(order_date) AS year,
           SUM(revenue) AS total_revenue
    FROM Orders
    GROUP BY YEAR(order_date)
)
SELECT y1.year,
       y1.total_revenue,
       y2.total_revenue AS prev_year_revenue,
       ROUND(
           (y1.total_revenue - y2.total_revenue) * 100.0 / y2.total_revenue, 
           2
       ) AS yoy_growth_pct
FROM yearly y1
LEFT JOIN yearly y2 ON y1.year = y2.year + 1
ORDER BY y1.year;
```

**Using LAG:**
```sql
WITH yearly AS (
    SELECT YEAR(order_date) AS year, SUM(revenue) AS total_revenue
    FROM Orders GROUP BY YEAR(order_date)
)
SELECT year, total_revenue,
       LAG(total_revenue) OVER (ORDER BY year) AS prev_revenue,
       ROUND(
           (total_revenue - LAG(total_revenue) OVER (ORDER BY year)) * 100.0 
           / LAG(total_revenue) OVER (ORDER BY year), 2
       ) AS yoy_growth_pct
FROM yearly;
```

---

## Problem 24: Find Users with Multiple Consecutive Failed Logins

**Difficulty:** Hard | **Frequency:** High (Security systems)

**Problem:** Find users who failed login 3+ consecutive times with no success in between.

```sql
CREATE TABLE LoginAttempts (
    id INT PRIMARY KEY,
    user_id INT,
    attempted_at TIMESTAMP,
    success BOOLEAN
);
```

**Solution (Gaps and Islands):**
```sql
WITH ordered AS (
    SELECT *,
        SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) 
            OVER (PARTITION BY user_id ORDER BY attempted_at) AS success_group
    FROM LoginAttempts
),
failed_streaks AS (
    SELECT user_id, success_group, COUNT(*) AS consecutive_failures
    FROM ordered
    WHERE success = FALSE
    GROUP BY user_id, success_group
    HAVING COUNT(*) >= 3
)
SELECT DISTINCT user_id FROM failed_streaks;
```

**Explanation:** Each success creates a new "island". Failed attempts between two successes belong to the same group. Count consecutive failures within each island.

---

## Problem 25: Retention Rate Calculation (Cohort Analysis)

**Difficulty:** Hard | **Frequency:** Very High (Product analytics)

**Problem:** Calculate Day-1, Day-7, and Day-30 retention by signup cohort.

```sql
CREATE TABLE UserActivity (
    user_id INT,
    activity_date DATE
);
CREATE TABLE Users (
    user_id INT,
    signup_date DATE
);
```

**Solution:**
```sql
WITH cohort AS (
    SELECT u.user_id, u.signup_date,
           DATEDIFF(a.activity_date, u.signup_date) AS day_number
    FROM Users u
    LEFT JOIN UserActivity a ON u.user_id = a.user_id
),
cohort_size AS (
    SELECT signup_date, COUNT(DISTINCT user_id) AS total_users
    FROM Users
    GROUP BY signup_date
)
SELECT 
    c.signup_date,
    cs.total_users,
    COUNT(DISTINCT CASE WHEN day_number = 1 THEN c.user_id END) AS day1_retained,
    COUNT(DISTINCT CASE WHEN day_number = 7 THEN c.user_id END) AS day7_retained,
    COUNT(DISTINCT CASE WHEN day_number = 30 THEN c.user_id END) AS day30_retained,
    ROUND(COUNT(DISTINCT CASE WHEN day_number = 1 THEN c.user_id END) * 100.0 / cs.total_users, 2) AS day1_pct,
    ROUND(COUNT(DISTINCT CASE WHEN day_number = 7 THEN c.user_id END) * 100.0 / cs.total_users, 2) AS day7_pct,
    ROUND(COUNT(DISTINCT CASE WHEN day_number = 30 THEN c.user_id END) * 100.0 / cs.total_users, 2) AS day30_pct
FROM cohort c
JOIN cohort_size cs ON c.signup_date = cs.signup_date
GROUP BY c.signup_date, cs.total_users
ORDER BY c.signup_date;
```

**Architect Discussion:**
- Cohort analysis is the #1 product analytics query
- At scale (billions of events), use approximate distinct counts (HyperLogLog)
- Pre-aggregate into cohort tables nightly (ETL/dbt models)
- Consider tools: Amplitude, Mixpanel use specialized time-series storage
- For real-time cohorts: Apache Druid, Apache Pinot, ClickHouse

---

## Key Patterns Summary

| Pattern | Problems | Core Technique |
|---------|----------|----------------|
| Finding Nth value | 1, 2, 7 | DENSE_RANK, LIMIT OFFSET |
| Gaps & Islands | 8, 13, 24 | ROW_NUMBER difference trick |
| Self-Join | 6, 11, 17 | Table joined to itself |
| Anti-Join | 5, 19 | NOT EXISTS, LEFT JOIN NULL |
| Running Aggregates | 21, 25 | Window functions with frames |
| Pivot/Unpivot | 22 | CASE WHEN aggregation |
| Consecutive detection | 8, 13, 17, 24 | LAG/LEAD or self-join |
