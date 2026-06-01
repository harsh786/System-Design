# SQL Mastery for Data Scientists & ML Engineers

## Why SQL is Essential

SQL is the **lingua franca of data**. Every data warehouse, most feature stores, and all relational databases speak SQL. You cannot be an effective ML engineer without SQL fluency.

```
┌─────────────────────────────────────────────────────┐
│              WHERE SQL IS USED IN ML                  │
├─────────────────────────────────────────────────────┤
│  • Feature engineering (80% of features start here) │
│  • Training data extraction                         │
│  • Data validation and quality checks               │
│  • A/B test analysis                                │
│  • Model monitoring queries                         │
│  • Business metric dashboards                       │
│  • Ad-hoc data exploration                          │
└─────────────────────────────────────────────────────┘
```

---

## Schema for Examples

```sql
-- E-commerce database schema
CREATE TABLE users (
    user_id       INT PRIMARY KEY,
    email         VARCHAR(255),
    signup_date   DATE,
    country       VARCHAR(50),
    plan_type     VARCHAR(20)  -- 'free', 'pro', 'enterprise'
);

CREATE TABLE orders (
    order_id      INT PRIMARY KEY,
    user_id       INT REFERENCES users(user_id),
    order_date    TIMESTAMP,
    total_amount  DECIMAL(10,2),
    status        VARCHAR(20)  -- 'completed', 'cancelled', 'refunded'
);

CREATE TABLE order_items (
    item_id       INT PRIMARY KEY,
    order_id      INT REFERENCES orders(order_id),
    product_id    INT REFERENCES products(product_id),
    quantity      INT,
    unit_price    DECIMAL(10,2)
);

CREATE TABLE products (
    product_id    INT PRIMARY KEY,
    name          VARCHAR(255),
    category      VARCHAR(100),
    price         DECIMAL(10,2),
    created_at    TIMESTAMP
);

CREATE TABLE events (
    event_id      BIGINT PRIMARY KEY,
    user_id       INT,
    event_type    VARCHAR(50),  -- 'page_view', 'click', 'purchase'
    event_time    TIMESTAMP,
    properties    JSONB
);
```

---

## 1. Basic SQL

```sql
-- SELECT with filtering and ordering
SELECT user_id, email, signup_date
FROM users
WHERE country = 'US'
  AND plan_type = 'pro'
  AND signup_date >= '2024-01-01'
ORDER BY signup_date DESC
LIMIT 100;

-- Pattern matching
SELECT * FROM users WHERE email LIKE '%@gmail.com';

-- NULL handling
SELECT * FROM users WHERE country IS NOT NULL;

-- CASE expressions
SELECT user_id,
       CASE 
           WHEN total_amount > 1000 THEN 'high_value'
           WHEN total_amount > 100  THEN 'medium_value'
           ELSE 'low_value'
       END AS customer_segment
FROM orders;
```

---

## 2. Joins Deep Dive

```
┌─────────────────────────────────────────────────┐
│                 JOIN TYPES                        │
├─────────────────────────────────────────────────┤
│  INNER JOIN    → Only matching rows             │
│  LEFT JOIN     → All left + matching right      │
│  RIGHT JOIN    → All right + matching left      │
│  FULL JOIN     → All rows from both             │
│  CROSS JOIN    → Cartesian product              │
│  SELF JOIN     → Table joined with itself       │
└─────────────────────────────────────────────────┘
```

```sql
-- INNER JOIN: Users who placed orders
SELECT u.user_id, u.email, COUNT(o.order_id) AS order_count
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id
GROUP BY u.user_id, u.email;

-- LEFT JOIN: All users, even without orders (churned users for ML)
SELECT u.user_id, u.email, 
       COALESCE(COUNT(o.order_id), 0) AS order_count
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
GROUP BY u.user_id, u.email;

-- SELF JOIN: Find users who signed up on the same day
SELECT a.user_id AS user_a, b.user_id AS user_b, a.signup_date
FROM users a
JOIN users b ON a.signup_date = b.signup_date AND a.user_id < b.user_id;

-- Anti-join pattern: Users who NEVER ordered
SELECT u.*
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
WHERE o.order_id IS NULL;
```

---

## 3. Aggregations

```sql
-- Basic aggregation
SELECT category,
       COUNT(*) AS product_count,
       AVG(price) AS avg_price,
       MIN(price) AS min_price,
       MAX(price) AS max_price,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price
FROM products
GROUP BY category
HAVING COUNT(*) > 10
ORDER BY avg_price DESC;

-- Multiple aggregation levels
SELECT country,
       plan_type,
       COUNT(*) AS user_count,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY country) AS pct_of_country
FROM users
GROUP BY country, plan_type;
```

---

## 4. Window Functions (Critical for ML Feature Engineering)

```sql
-- ROW_NUMBER, RANK, DENSE_RANK
SELECT user_id, order_date, total_amount,
       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS order_sequence,
       RANK() OVER (ORDER BY total_amount DESC) AS amount_rank
FROM orders;

-- LEAD and LAG: Time between purchases
SELECT user_id, order_date, total_amount,
       LAG(order_date) OVER (PARTITION BY user_id ORDER BY order_date) AS prev_order_date,
       order_date - LAG(order_date) OVER (PARTITION BY user_id ORDER BY order_date) AS days_between_orders
FROM orders;

-- Running totals and moving averages
SELECT user_id, order_date, total_amount,
       SUM(total_amount) OVER (
           PARTITION BY user_id 
           ORDER BY order_date 
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS cumulative_spend,
       AVG(total_amount) OVER (
           PARTITION BY user_id 
           ORDER BY order_date 
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
       ) AS moving_avg_3_orders
FROM orders;

-- FIRST_VALUE, LAST_VALUE, NTH_VALUE
SELECT user_id, order_date, total_amount,
       FIRST_VALUE(total_amount) OVER (
           PARTITION BY user_id ORDER BY order_date
       ) AS first_order_amount,
       total_amount - FIRST_VALUE(total_amount) OVER (
           PARTITION BY user_id ORDER BY order_date
       ) AS amount_change_from_first
FROM orders;
```

---

## 5. CTEs and Subqueries

```sql
-- CTE for readability
WITH user_metrics AS (
    SELECT user_id,
           COUNT(*) AS total_orders,
           SUM(total_amount) AS lifetime_value,
           MIN(order_date) AS first_order,
           MAX(order_date) AS last_order
    FROM orders
    WHERE status = 'completed'
    GROUP BY user_id
),
user_segments AS (
    SELECT *,
           CASE
               WHEN lifetime_value > 5000 THEN 'whale'
               WHEN lifetime_value > 1000 THEN 'regular'
               ELSE 'casual'
           END AS segment,
           CURRENT_DATE - last_order::date AS days_since_last_order
    FROM user_metrics
)
SELECT segment,
       COUNT(*) AS user_count,
       AVG(lifetime_value) AS avg_ltv,
       AVG(days_since_last_order) AS avg_recency
FROM user_segments
GROUP BY segment;

-- Recursive CTE: Generate date series
WITH RECURSIVE date_series AS (
    SELECT '2024-01-01'::date AS dt
    UNION ALL
    SELECT dt + INTERVAL '1 day'
    FROM date_series
    WHERE dt < '2024-12-31'
)
SELECT ds.dt, COALESCE(COUNT(o.order_id), 0) AS daily_orders
FROM date_series ds
LEFT JOIN orders o ON o.order_date::date = ds.dt
GROUP BY ds.dt
ORDER BY ds.dt;
```

---

## 6. Set Operations

```sql
-- Users who bought AND viewed but never purchased category X
(SELECT DISTINCT user_id FROM events WHERE event_type = 'page_view')
INTERSECT
(SELECT DISTINCT user_id FROM orders)
EXCEPT
(SELECT DISTINCT o.user_id 
 FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
 JOIN products p ON oi.product_id = p.product_id
 WHERE p.category = 'Electronics');
```

---

## 7. SQL for ML Feature Engineering

### Time-Windowed Aggregations (Most Common ML Features)

```sql
-- Features at multiple time windows
SELECT u.user_id,
       -- 7-day features
       COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 7 THEN 1 END) AS orders_7d,
       SUM(CASE WHEN o.order_date >= CURRENT_DATE - 7 THEN o.total_amount ELSE 0 END) AS spend_7d,
       -- 30-day features
       COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 30 THEN 1 END) AS orders_30d,
       SUM(CASE WHEN o.order_date >= CURRENT_DATE - 30 THEN o.total_amount ELSE 0 END) AS spend_30d,
       -- 90-day features
       COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 90 THEN 1 END) AS orders_90d,
       -- Ratios
       CASE WHEN COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 30 THEN 1 END) > 0
            THEN COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 7 THEN 1 END)::float /
                 COUNT(CASE WHEN o.order_date >= CURRENT_DATE - 30 THEN 1 END)
            ELSE 0 END AS order_acceleration
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'completed'
GROUP BY u.user_id;
```

### Sessionization

```sql
-- Define sessions with 30-min inactivity gap
WITH events_with_gap AS (
    SELECT *,
           EXTRACT(EPOCH FROM event_time - LAG(event_time) OVER (
               PARTITION BY user_id ORDER BY event_time
           )) / 60 AS minutes_since_last
    FROM events
),
sessions AS (
    SELECT *,
           SUM(CASE WHEN minutes_since_last > 30 OR minutes_since_last IS NULL 
                    THEN 1 ELSE 0 END) 
               OVER (PARTITION BY user_id ORDER BY event_time) AS session_id
    FROM events_with_gap
)
SELECT user_id, session_id,
       MIN(event_time) AS session_start,
       MAX(event_time) AS session_end,
       COUNT(*) AS events_in_session,
       EXTRACT(EPOCH FROM MAX(event_time) - MIN(event_time)) / 60 AS session_duration_min
FROM sessions
GROUP BY user_id, session_id;
```

### Funnel Analysis

```sql
-- Conversion funnel: view → cart → purchase
WITH funnel AS (
    SELECT user_id,
           MAX(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) AS viewed,
           MAX(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS carted,
           MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchased
    FROM events
    WHERE event_time >= CURRENT_DATE - 30
    GROUP BY user_id
)
SELECT 
    COUNT(*) AS total_users,
    SUM(viewed) AS step1_viewed,
    SUM(carted) AS step2_carted,
    SUM(purchased) AS step3_purchased,
    ROUND(SUM(carted)::numeric / NULLIF(SUM(viewed), 0) * 100, 1) AS view_to_cart_pct,
    ROUND(SUM(purchased)::numeric / NULLIF(SUM(carted), 0) * 100, 1) AS cart_to_purchase_pct
FROM funnel;
```

### Cohort Analysis

```sql
-- Monthly retention cohorts
WITH user_cohorts AS (
    SELECT user_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM users
),
user_activity AS (
    SELECT user_id, DATE_TRUNC('month', order_date) AS activity_month
    FROM orders
    GROUP BY user_id, DATE_TRUNC('month', order_date)
)
SELECT c.cohort_month,
       a.activity_month,
       EXTRACT(MONTH FROM AGE(a.activity_month, c.cohort_month)) AS months_since_signup,
       COUNT(DISTINCT a.user_id) AS active_users,
       COUNT(DISTINCT a.user_id)::float / 
           COUNT(DISTINCT c.user_id) FILTER (WHERE c.cohort_month = c.cohort_month) AS retention_rate
FROM user_cohorts c
LEFT JOIN user_activity a ON c.user_id = a.user_id
GROUP BY c.cohort_month, a.activity_month
ORDER BY c.cohort_month, a.activity_month;
```

---

## 8. Performance Optimization

```sql
-- EXPLAIN ANALYZE to understand query plans
EXPLAIN ANALYZE
SELECT u.user_id, COUNT(o.order_id)
FROM users u
JOIN orders o ON u.user_id = o.user_id
WHERE o.order_date >= '2024-01-01'
GROUP BY u.user_id;

-- Create indexes for common query patterns
CREATE INDEX idx_orders_user_date ON orders(user_id, order_date DESC);
CREATE INDEX idx_events_user_time ON events(user_id, event_time DESC);
CREATE INDEX idx_orders_status ON orders(status) WHERE status = 'completed';  -- partial index
```

### Optimization Patterns

| Anti-Pattern | Better Approach |
|---|---|
| `SELECT *` | Select only needed columns |
| `WHERE function(col) = val` | `WHERE col = inverse_function(val)` |
| Correlated subquery in SELECT | JOIN or window function |
| `NOT IN (subquery with NULLs)` | `NOT EXISTS` |
| Multiple sequential scans | Combined CASE statements |
| `DISTINCT` on large result | Proper GROUP BY or EXISTS |

---

## 9. SQL Across Engines

| Feature | PostgreSQL | BigQuery | Spark SQL | DuckDB |
|---------|-----------|----------|-----------|--------|
| Window functions | Full support | Full support | Full support | Full support |
| LATERAL JOIN | Yes | CROSS JOIN UNNEST | Lateral view | Yes |
| JSON | JSONB operators | JSON functions | get_json_object | JSON extract |
| Arrays | ARRAY type | ARRAY type | array() | LIST type |
| Approx counts | - | APPROX_COUNT_DISTINCT | approx_count_distinct | - |
| Partitioned tables | Declarative | Native | Native | - |

```sql
-- BigQuery specific: UNNEST arrays
SELECT user_id, tag
FROM users, UNNEST(tags) AS tag
WHERE tag = 'premium';

-- Spark SQL: Explode nested structures
SELECT user_id, explode(purchase_history) AS purchase
FROM user_profiles;

-- DuckDB: Direct Parquet/CSV queries
SELECT * FROM read_parquet('s3://bucket/data/*.parquet')
WHERE date >= '2024-01-01';
```

---

## 10. Practice Problems

### Problem 1: Second Highest Salary
```sql
-- Solution using DENSE_RANK
SELECT salary FROM (
    SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS rnk
    FROM employees
) t WHERE rnk = 2;
```

### Problem 2: Consecutive Login Days
```sql
WITH login_groups AS (
    SELECT user_id, login_date,
           login_date - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date)::int AS grp
    FROM (SELECT DISTINCT user_id, login_date::date AS login_date FROM logins) t
)
SELECT user_id, COUNT(*) AS consecutive_days
FROM login_groups
GROUP BY user_id, grp
HAVING COUNT(*) >= 7;
```

### Problem 3: Year-over-Year Growth
```sql
WITH monthly_revenue AS (
    SELECT DATE_TRUNC('month', order_date) AS month,
           SUM(total_amount) AS revenue
    FROM orders WHERE status = 'completed'
    GROUP BY 1
)
SELECT month, revenue,
       LAG(revenue, 12) OVER (ORDER BY month) AS revenue_last_year,
       ROUND((revenue - LAG(revenue, 12) OVER (ORDER BY month)) / 
             NULLIF(LAG(revenue, 12) OVER (ORDER BY month), 0) * 100, 1) AS yoy_growth_pct
FROM monthly_revenue;
```

### Problem 4: Find Gaps in Sequential IDs
```sql
SELECT prev_id + 1 AS gap_start, order_id - 1 AS gap_end
FROM (
    SELECT order_id, LAG(order_id) OVER (ORDER BY order_id) AS prev_id
    FROM orders
) t
WHERE order_id - prev_id > 1;
```

### Problem 5: Median per Group (without PERCENTILE_CONT)
```sql
WITH ranked AS (
    SELECT category, price,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY price) AS rn,
           COUNT(*) OVER (PARTITION BY category) AS cnt
    FROM products
)
SELECT category, AVG(price) AS median_price
FROM ranked
WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0))
GROUP BY category;
```

---

## Interview Questions

1. **What's the difference between WHERE and HAVING?**
   - WHERE filters rows before aggregation; HAVING filters groups after aggregation.

2. **Explain the order of SQL execution.**
   - FROM → WHERE → GROUP BY → HAVING → SELECT → DISTINCT → ORDER BY → LIMIT

3. **When would you use a window function instead of GROUP BY?**
   - When you need aggregation without collapsing rows (keep individual row detail).

4. **What's the difference between RANK and DENSE_RANK?**
   - RANK leaves gaps after ties (1,1,3); DENSE_RANK doesn't (1,1,2).

5. **How do you handle NULL in aggregations?**
   - COUNT(*) includes NULLs; COUNT(col) excludes them. Use COALESCE for defaults.

6. **What's a correlated subquery and why avoid it?**
   - Subquery that references outer query; executes once per outer row (O(n²)).

7. **Explain index selectivity.**
   - High selectivity = column has many distinct values → index is useful. Low selectivity (e.g., boolean) → full scan may be faster.

8. **What's the difference between DELETE, TRUNCATE, and DROP?**
   - DELETE: row-by-row, logged, WHERE clause. TRUNCATE: fast, minimal logging. DROP: removes table.

9. **How do CTEs differ from temp tables?**
   - CTEs are query-scoped, not materialized (usually). Temp tables persist in session, can be indexed.

10. **Explain query plan: Seq Scan vs Index Scan vs Bitmap Scan.**
    - Seq Scan: reads all rows. Index Scan: uses index for few rows. Bitmap Scan: index for moderate rows, then heap fetch.

---

## Common Anti-Patterns

```sql
-- ❌ Using OFFSET for pagination (slow at high offsets)
SELECT * FROM orders ORDER BY order_id LIMIT 20 OFFSET 100000;

-- ✅ Keyset pagination
SELECT * FROM orders WHERE order_id > 100000 ORDER BY order_id LIMIT 20;

-- ❌ N+1 queries in application code
-- For each user: SELECT * FROM orders WHERE user_id = ?

-- ✅ Batch query
SELECT * FROM orders WHERE user_id IN (1, 2, 3, ...);

-- ❌ Implicit type casting killing index usage
SELECT * FROM orders WHERE order_id = '12345';  -- string vs int

-- ✅ Match types
SELECT * FROM orders WHERE order_id = 12345;
```
