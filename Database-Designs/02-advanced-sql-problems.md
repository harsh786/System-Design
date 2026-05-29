# Advanced SQL Problems (Problems 26-50)

## Window Functions, CTEs, Recursive Queries, and Complex Analytics

---

## Problem 26: Moving Average (7-Day Rolling Average)

**Difficulty:** Medium | **Frequency:** Very High (Finance, Metrics)

**Problem:** Calculate 7-day moving average of daily revenue.

```sql
SELECT order_date,
       daily_revenue,
       AVG(daily_revenue) OVER (
           ORDER BY order_date
           ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS moving_avg_7d
FROM (
    SELECT order_date, SUM(amount) AS daily_revenue
    FROM Orders
    GROUP BY order_date
) daily
ORDER BY order_date;
```

**ROWS vs RANGE for Moving Average:**
```sql
-- ROWS: Exactly 7 physical rows (even if dates are missing)
ROWS BETWEEN 6 PRECEDING AND CURRENT ROW

-- RANGE: All rows within 7-day range (handles missing dates correctly)
RANGE BETWEEN INTERVAL '6' DAY PRECEDING AND CURRENT ROW
```

**Architect Insight:**
- For dashboards, pre-compute in materialized views refreshed hourly
- At high cardinality (per-user metrics), use approximate streaming algorithms
- TimescaleDB `time_bucket_gapfill()` handles missing intervals automatically

---

## Problem 27: Sessionization (Group Events into Sessions)

**Difficulty:** Hard | **Frequency:** Very High (Analytics, Product)

**Problem:** Group user events into sessions where a session ends after 30 minutes of inactivity.

```sql
WITH time_gaps AS (
    SELECT user_id, event_time, event_type,
           LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_time,
           CASE 
               WHEN TIMESTAMPDIFF(MINUTE, 
                   LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time), 
                   event_time) > 30 
               OR LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) IS NULL
               THEN 1 
               ELSE 0 
           END AS new_session
    FROM UserEvents
),
sessions AS (
    SELECT *,
           SUM(new_session) OVER (PARTITION BY user_id ORDER BY event_time) AS session_id
    FROM time_gaps
)
SELECT user_id, session_id,
       MIN(event_time) AS session_start,
       MAX(event_time) AS session_end,
       COUNT(*) AS events_in_session,
       TIMESTAMPDIFF(MINUTE, MIN(event_time), MAX(event_time)) AS session_duration_min
FROM sessions
GROUP BY user_id, session_id;
```

**Technique Breakdown:**
1. Use `LAG` to find time gap between consecutive events
2. Mark start of new session when gap > threshold
3. `SUM` of session-start flags creates incrementing session IDs
4. Group by session_id for session-level metrics

**Architect Discussion:**
- This is the core of Google Analytics session computation
- At scale: Flink/Spark Structured Streaming with session windows
- Apache Beam has native session window support
- Consider writing to a pre-computed sessions table via streaming pipeline

---

## Problem 28: Funnel Analysis (Conversion Through Steps)

**Difficulty:** Hard | **Frequency:** Very High (E-commerce, SaaS)

**Problem:** Calculate conversion rate through a multi-step funnel: View → Cart → Checkout → Purchase.

```sql
WITH funnel AS (
    SELECT user_id,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS viewed,
        MAX(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS added_to_cart,
        MAX(CASE WHEN event_type = 'checkout' THEN 1 ELSE 0 END) AS checked_out,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchased
    FROM UserEvents
    WHERE event_date BETWEEN '2024-01-01' AND '2024-01-31'
    GROUP BY user_id
)
SELECT 
    COUNT(*) AS total_users,
    SUM(viewed) AS step1_view,
    SUM(added_to_cart) AS step2_cart,
    SUM(checked_out) AS step3_checkout,
    SUM(purchased) AS step4_purchase,
    ROUND(SUM(added_to_cart) * 100.0 / SUM(viewed), 2) AS view_to_cart_pct,
    ROUND(SUM(checked_out) * 100.0 / SUM(added_to_cart), 2) AS cart_to_checkout_pct,
    ROUND(SUM(purchased) * 100.0 / SUM(checked_out), 2) AS checkout_to_purchase_pct,
    ROUND(SUM(purchased) * 100.0 / SUM(viewed), 2) AS overall_conversion_pct
FROM funnel;
```

**Ordered Funnel (user must complete steps in order):**
```sql
WITH ordered_events AS (
    SELECT user_id, event_type, event_time,
           ROW_NUMBER() OVER (PARTITION BY user_id, event_type ORDER BY event_time) AS rn
    FROM UserEvents
),
first_events AS (
    SELECT user_id, event_type, event_time
    FROM ordered_events WHERE rn = 1
),
funnel AS (
    SELECT 
        v.user_id,
        v.event_time AS view_time,
        c.event_time AS cart_time,
        co.event_time AS checkout_time,
        p.event_time AS purchase_time
    FROM first_events v
    LEFT JOIN first_events c ON v.user_id = c.user_id 
        AND c.event_type = 'add_to_cart' AND c.event_time > v.event_time
    LEFT JOIN first_events co ON v.user_id = co.user_id 
        AND co.event_type = 'checkout' AND co.event_time > c.event_time
    LEFT JOIN first_events p ON v.user_id = p.user_id 
        AND p.event_type = 'purchase' AND p.event_time > co.event_time
    WHERE v.event_type = 'view'
)
SELECT
    COUNT(*) AS viewed,
    COUNT(cart_time) AS added_to_cart,
    COUNT(checkout_time) AS checked_out,
    COUNT(purchase_time) AS purchased
FROM funnel;
```

---

## Problem 29: Recursive CTE - Organizational Hierarchy

**Difficulty:** Hard | **Frequency:** Very High (Enterprise systems)

**Problem:** Find all reports (direct and indirect) under a given manager, with their level in hierarchy.

```sql
WITH RECURSIVE org_tree AS (
    -- Anchor: Start with the target manager
    SELECT id, name, manager_id, 0 AS level, 
           CAST(name AS CHAR(1000)) AS path
    FROM Employees
    WHERE id = 1  -- Starting manager
    
    UNION ALL
    
    -- Recursive: Find all direct reports of current level
    SELECT e.id, e.name, e.manager_id, ot.level + 1,
           CONCAT(ot.path, ' → ', e.name)
    FROM Employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY level, name;
```

**Find Total Team Size for Each Manager:**
```sql
WITH RECURSIVE org_tree AS (
    SELECT id, name, manager_id, id AS root_manager
    FROM Employees
    
    UNION ALL
    
    SELECT e.id, e.name, e.manager_id, ot.root_manager
    FROM Employees e
    JOIN org_tree ot ON e.manager_id = ot.id
    WHERE e.id != ot.root_manager  -- Prevent counting self
)
SELECT root_manager, m.name, COUNT(*) - 1 AS team_size
FROM org_tree ot
JOIN Employees m ON ot.root_manager = m.id
GROUP BY root_manager, m.name
ORDER BY team_size DESC;
```

**Architect: Hierarchy Storage Patterns:**

| Pattern | Read | Write | Use Case |
|---------|------|-------|----------|
| Adjacency List | O(n) recursive | O(1) | Simple org charts |
| Nested Sets | O(1) subtree | O(n) restructure | Read-heavy taxonomies |
| Materialized Path | O(1) with LIKE | O(depth) | File systems, URLs |
| Closure Table | O(1) any query | O(depth) inserts | Complex hierarchies |

---

## Problem 30: Recursive CTE - Bill of Materials (BOM Explosion)

**Difficulty:** Hard | **Frequency:** High (Manufacturing, ERP)

**Problem:** Calculate total cost of a product including all sub-components recursively.

```sql
CREATE TABLE BOM (
    parent_part_id INT,
    child_part_id INT,
    quantity INT
);
CREATE TABLE Parts (
    part_id INT PRIMARY KEY,
    name VARCHAR(100),
    unit_cost DECIMAL(10,2)
);
```

**Solution:**
```sql
WITH RECURSIVE bom_exploded AS (
    -- Anchor: Top-level product
    SELECT b.parent_part_id AS root_product,
           b.child_part_id,
           b.quantity,
           1 AS level
    FROM BOM b
    WHERE b.parent_part_id = 100  -- Target product
    
    UNION ALL
    
    -- Recursive: Sub-components
    SELECT be.root_product,
           b.child_part_id,
           be.quantity * b.quantity AS quantity,  -- Multiply quantities down
           be.level + 1
    FROM bom_exploded be
    JOIN BOM b ON be.child_part_id = b.parent_part_id
)
SELECT be.root_product,
       SUM(be.quantity * p.unit_cost) AS total_cost
FROM bom_exploded be
JOIN Parts p ON be.child_part_id = p.part_id
WHERE be.child_part_id NOT IN (SELECT DISTINCT parent_part_id FROM BOM)  -- Leaf parts only
GROUP BY be.root_product;
```

---

## Problem 31: Find Mutual Friends

**Difficulty:** Hard | **Frequency:** Very High (Social Networks)

**Problem:** Find mutual friends between two users.

```sql
CREATE TABLE Friendships (user_id INT, friend_id INT);
-- Assume bidirectional: if (A,B) exists, (B,A) also exists
```

**Solution:**
```sql
SELECT f1.friend_id AS mutual_friend
FROM Friendships f1
JOIN Friendships f2 ON f1.friend_id = f2.friend_id
WHERE f1.user_id = 1    -- User A
  AND f2.user_id = 2    -- User B
  AND f1.friend_id NOT IN (1, 2);  -- Exclude the two users themselves
```

**Friend Recommendations (People You May Know):**
```sql
-- Friends of friends who are not already your friends
WITH my_friends AS (
    SELECT friend_id FROM Friendships WHERE user_id = 1
),
friends_of_friends AS (
    SELECT f.friend_id AS suggested, COUNT(*) AS mutual_count
    FROM Friendships f
    WHERE f.user_id IN (SELECT friend_id FROM my_friends)
      AND f.friend_id != 1
      AND f.friend_id NOT IN (SELECT friend_id FROM my_friends)
    GROUP BY f.friend_id
)
SELECT suggested, mutual_count
FROM friends_of_friends
ORDER BY mutual_count DESC
LIMIT 10;
```

---

## Problem 32: Detect Circular References

**Difficulty:** Hard | **Frequency:** Medium (Data integrity)

**Problem:** Detect cycles in a self-referencing table (e.g., manager reporting to their own report).

```sql
WITH RECURSIVE chain AS (
    SELECT id, manager_id, CAST(id AS CHAR(1000)) AS path, 0 AS is_cycle
    FROM Employees
    WHERE id = @start_id
    
    UNION ALL
    
    SELECT e.id, e.manager_id,
           CONCAT(c.path, ',', e.id),
           CASE WHEN FIND_IN_SET(e.id, c.path) > 0 THEN 1 ELSE 0 END
    FROM Employees e
    JOIN chain c ON e.id = c.manager_id
    WHERE c.is_cycle = 0
)
SELECT * FROM chain WHERE is_cycle = 1;
```

**PostgreSQL (cleaner with array):**
```sql
WITH RECURSIVE chain AS (
    SELECT id, manager_id, ARRAY[id] AS path, FALSE AS is_cycle
    FROM Employees
    
    UNION ALL
    
    SELECT e.id, e.manager_id, c.path || e.id,
           e.id = ANY(c.path)
    FROM Employees e
    JOIN chain c ON e.id = c.manager_id
    WHERE NOT c.is_cycle
)
SELECT * FROM chain WHERE is_cycle;
```

---

## Problem 33: Unpivot - Columns to Rows

**Difficulty:** Medium | **Frequency:** High

**Problem:** Transform columnar data back to rows.

```sql
-- Source: Products table with Q1, Q2, Q3, Q4 columns
CREATE TABLE QuarterlySales (
    product VARCHAR(50),
    Q1 DECIMAL, Q2 DECIMAL, Q3 DECIMAL, Q4 DECIMAL
);
```

**Solution (UNION ALL approach):**
```sql
SELECT product, 'Q1' AS quarter, Q1 AS sales FROM QuarterlySales
UNION ALL
SELECT product, 'Q2', Q2 FROM QuarterlySales
UNION ALL
SELECT product, 'Q3', Q3 FROM QuarterlySales
UNION ALL
SELECT product, 'Q4', Q4 FROM QuarterlySales
ORDER BY product, quarter;
```

**SQL Server UNPIVOT:**
```sql
SELECT product, quarter, sales
FROM QuarterlySales
UNPIVOT (sales FOR quarter IN (Q1, Q2, Q3, Q4)) AS unpvt;
```

**PostgreSQL LATERAL:**
```sql
SELECT product, quarter, sales
FROM QuarterlySales,
LATERAL (VALUES ('Q1', Q1), ('Q2', Q2), ('Q3', Q3), ('Q4', Q4)) 
    AS t(quarter, sales);
```

---

## Problem 34: MATCH_RECOGNIZE - Pattern Matching in Sequences

**Difficulty:** Expert | **Frequency:** Medium (Oracle, Snowflake)

**Problem:** Find V-shaped stock price patterns (price drops then rises).

```sql
-- Oracle/Snowflake MATCH_RECOGNIZE
SELECT *
FROM StockPrices
MATCH_RECOGNIZE (
    PARTITION BY symbol
    ORDER BY trade_date
    MEASURES
        FIRST(DOWN.trade_date) AS start_date,
        LAST(UP.trade_date) AS end_date,
        FIRST(DOWN.price) AS start_price,
        LAST(DOWN.price) AS bottom_price,
        LAST(UP.price) AS end_price
    ONE ROW PER MATCH
    PATTERN (DOWN+ UP+)
    DEFINE
        DOWN AS price < PREV(price),
        UP AS price > PREV(price)
);
```

**Without MATCH_RECOGNIZE (using window functions):**
```sql
WITH price_direction AS (
    SELECT *,
        CASE 
            WHEN price < LAG(price) OVER (PARTITION BY symbol ORDER BY trade_date) THEN 'DOWN'
            WHEN price > LAG(price) OVER (PARTITION BY symbol ORDER BY trade_date) THEN 'UP'
            ELSE 'FLAT'
        END AS direction
    FROM StockPrices
),
direction_groups AS (
    SELECT *,
        SUM(CASE WHEN direction != LAG(direction) OVER (PARTITION BY symbol ORDER BY trade_date) 
            THEN 1 ELSE 0 END) OVER (PARTITION BY symbol ORDER BY trade_date) AS grp
    FROM price_direction
)
-- Identify DOWN groups followed by UP groups
SELECT symbol, MIN(trade_date) AS pattern_start, MAX(trade_date) AS pattern_end
FROM direction_groups
-- Complex logic to find DOWN→UP transitions
GROUP BY symbol, grp;
```

---

## Problem 35: Histogram / Distribution Buckets

**Difficulty:** Medium | **Frequency:** High (Analytics)

**Problem:** Create salary distribution histogram with custom buckets.

```sql
SELECT 
    CASE 
        WHEN salary < 30000 THEN '0-30K'
        WHEN salary < 50000 THEN '30K-50K'
        WHEN salary < 75000 THEN '50K-75K'
        WHEN salary < 100000 THEN '75K-100K'
        ELSE '100K+'
    END AS salary_band,
    COUNT(*) AS employee_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM Employees
GROUP BY 1
ORDER BY MIN(salary);
```

**Dynamic Width Buckets (PostgreSQL):**
```sql
SELECT width_bucket(salary, 0, 200000, 10) AS bucket,
       COUNT(*) AS count,
       MIN(salary) AS bucket_min,
       MAX(salary) AS bucket_max
FROM Employees
GROUP BY 1
ORDER BY 1;
```

**Percentile Distribution:**
```sql
SELECT 
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary) AS p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY salary) AS median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary) AS p75,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY salary) AS p90,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY salary) AS p99
FROM Employees;
```

---

## Problem 36: Find Missing Ranges / Gaps in Sequences

**Difficulty:** Medium | **Frequency:** High (Data quality)

**Problem:** Find gaps in a sequence of IDs or dates.

```sql
-- Find missing dates in a daily report
WITH date_range AS (
    SELECT generate_series(
        (SELECT MIN(report_date) FROM DailyReports),
        (SELECT MAX(report_date) FROM DailyReports),
        '1 day'::interval
    )::date AS expected_date
)
SELECT expected_date AS missing_date
FROM date_range dr
LEFT JOIN DailyReports r ON dr.expected_date = r.report_date
WHERE r.report_date IS NULL;
```

**Find gaps in numeric sequences:**
```sql
WITH gaps AS (
    SELECT id,
           LEAD(id) OVER (ORDER BY id) AS next_id
    FROM Numbers
)
SELECT id + 1 AS gap_start,
       next_id - 1 AS gap_end
FROM gaps
WHERE next_id - id > 1;
```

---

## Problem 37: Self-Join for Pair Matching

**Difficulty:** Medium | **Frequency:** High

**Problem:** Find all pairs of students in the same class who scored within 5 points of each other.

```sql
SELECT s1.student_name AS student1,
       s2.student_name AS student2,
       s1.class_id,
       s1.score AS score1,
       s2.score AS score2,
       ABS(s1.score - s2.score) AS score_diff
FROM Students s1
JOIN Students s2 ON s1.class_id = s2.class_id
    AND s1.student_id < s2.student_id  -- Avoid duplicates and self-pairs
WHERE ABS(s1.score - s2.score) <= 5
ORDER BY s1.class_id, score_diff;
```

**Key:** `s1.id < s2.id` prevents (A,B) and (B,A) duplicates and self-matches.

---

## Problem 38: Recursive Date Generation (Calendar Table)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Generate a date dimension table for analytics.

```sql
WITH RECURSIVE calendar AS (
    SELECT DATE '2024-01-01' AS dt
    UNION ALL
    SELECT dt + INTERVAL '1 day'
    FROM calendar
    WHERE dt < '2024-12-31'
)
SELECT 
    dt AS date,
    EXTRACT(YEAR FROM dt) AS year,
    EXTRACT(QUARTER FROM dt) AS quarter,
    EXTRACT(MONTH FROM dt) AS month,
    EXTRACT(DOW FROM dt) AS day_of_week,
    EXTRACT(DOY FROM dt) AS day_of_year,
    CASE WHEN EXTRACT(DOW FROM dt) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
    TO_CHAR(dt, 'Day') AS day_name,
    TO_CHAR(dt, 'Month') AS month_name
FROM calendar;
```

**Architect:** Every data warehouse needs a calendar/date dimension table. Pre-generate it and add business-specific fields (fiscal year, holidays, business days).

---

## Problem 39: Multi-Level Aggregation (GROUPING SETS, CUBE, ROLLUP)

**Difficulty:** Medium | **Frequency:** High (OLAP, Reporting)

**Problem:** Generate sales report with subtotals and grand total.

```sql
-- ROLLUP: Hierarchical subtotals
SELECT region, country, city, SUM(revenue) AS total_revenue
FROM Sales
GROUP BY ROLLUP (region, country, city);
-- Produces: (region, country, city), (region, country, NULL), (region, NULL, NULL), (NULL, NULL, NULL)

-- CUBE: All possible subtotal combinations
SELECT region, product_category, SUM(revenue)
FROM Sales
GROUP BY CUBE (region, product_category);
-- Produces: all 2^n combinations

-- GROUPING SETS: Specific combinations only
SELECT region, product_category, EXTRACT(YEAR FROM sale_date) AS year,
       SUM(revenue) AS total_revenue
FROM Sales
GROUP BY GROUPING SETS (
    (region, product_category),
    (region, year),
    (product_category),
    ()  -- Grand total
);
```

**Using GROUPING() to identify subtotal rows:**
```sql
SELECT 
    CASE WHEN GROUPING(region) = 1 THEN 'ALL REGIONS' ELSE region END AS region,
    CASE WHEN GROUPING(product) = 1 THEN 'ALL PRODUCTS' ELSE product END AS product,
    SUM(revenue) AS total_revenue,
    GROUPING(region) AS is_region_total,
    GROUPING(product) AS is_product_total
FROM Sales
GROUP BY ROLLUP (region, product);
```

---

## Problem 40: Conditional Aggregation with FILTER (PostgreSQL)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Calculate multiple conditional aggregates efficiently.

```sql
-- PostgreSQL FILTER clause (cleaner than CASE)
SELECT 
    department,
    COUNT(*) FILTER (WHERE status = 'active') AS active_count,
    COUNT(*) FILTER (WHERE status = 'inactive') AS inactive_count,
    AVG(salary) FILTER (WHERE tenure_years >= 5) AS avg_salary_senior,
    AVG(salary) FILTER (WHERE tenure_years < 2) AS avg_salary_junior,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) 
        FILTER (WHERE gender = 'F') AS median_salary_female,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) 
        FILTER (WHERE gender = 'M') AS median_salary_male
FROM Employees
GROUP BY department;
```

**Cross-database equivalent (CASE WHEN):**
```sql
SELECT department,
    COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_count,
    AVG(CASE WHEN tenure_years >= 5 THEN salary END) AS avg_salary_senior
FROM Employees
GROUP BY department;
```

---

## Problem 41: Top-N Per Group (Most Popular Items per Category)

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Find top 3 best-selling products in each category.

```sql
WITH ranked AS (
    SELECT p.category, p.product_name,
           SUM(o.quantity) AS total_sold,
           ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(o.quantity) DESC) AS rn
    FROM Products p
    JOIN OrderItems o ON p.product_id = o.product_id
    GROUP BY p.category, p.product_name
)
SELECT category, product_name, total_sold
FROM ranked
WHERE rn <= 3
ORDER BY category, rn;
```

**Using LATERAL (PostgreSQL) - often faster:**
```sql
SELECT c.category_name, t.product_name, t.total_sold
FROM Categories c
CROSS JOIN LATERAL (
    SELECT p.product_name, SUM(oi.quantity) AS total_sold
    FROM Products p
    JOIN OrderItems oi ON p.product_id = oi.product_id
    WHERE p.category_id = c.id
    GROUP BY p.product_name
    ORDER BY total_sold DESC
    LIMIT 3
) t;
```

**Architect: LATERAL vs Window Function Performance:**
- LATERAL with LIMIT: Stops scanning after finding top-N per group
- Window function: Must process ALL rows then filter
- For large datasets with many groups, LATERAL is significantly faster
- Requires index on `(category_id, quantity DESC)` or similar

---

## Problem 42: Time-Weighted Average

**Difficulty:** Hard | **Frequency:** High (IoT, Financial)

**Problem:** Calculate time-weighted average of sensor readings (weight by duration each value was active).

```sql
WITH intervals AS (
    SELECT sensor_id, value, recorded_at,
           LEAD(recorded_at) OVER (PARTITION BY sensor_id ORDER BY recorded_at) AS next_time,
           EXTRACT(EPOCH FROM (
               LEAD(recorded_at) OVER (PARTITION BY sensor_id ORDER BY recorded_at) - recorded_at
           )) AS duration_seconds
    FROM SensorReadings
)
SELECT sensor_id,
       SUM(value * duration_seconds) / SUM(duration_seconds) AS time_weighted_avg
FROM intervals
WHERE duration_seconds IS NOT NULL
GROUP BY sensor_id;
```

---

## Problem 43: Recursive CTE - Shortest Path in Graph

**Difficulty:** Expert | **Frequency:** Medium (Graph problems in SQL)

**Problem:** Find shortest path between two nodes in a graph stored in SQL.

```sql
CREATE TABLE Edges (from_node INT, to_node INT, weight INT);
```

**Solution (BFS with recursive CTE):**
```sql
WITH RECURSIVE paths AS (
    -- Start from source
    SELECT from_node, to_node, weight AS total_weight,
           ARRAY[from_node, to_node] AS path,
           1 AS hops
    FROM Edges
    WHERE from_node = 1  -- Source node
    
    UNION ALL
    
    -- Extend paths
    SELECT p.from_node, e.to_node, p.total_weight + e.weight,
           p.path || e.to_node,
           p.hops + 1
    FROM paths p
    JOIN Edges e ON p.to_node = e.from_node
    WHERE NOT (e.to_node = ANY(p.path))  -- Prevent cycles
      AND p.hops < 10  -- Max depth safety
)
SELECT path, total_weight
FROM paths
WHERE to_node = 5  -- Destination node
ORDER BY total_weight
LIMIT 1;
```

**Architect Insight:** SQL is not ideal for graph traversal. For production:
- Use Neo4j, Amazon Neptune, or JanusGraph
- PostgreSQL AGE extension adds Cypher support
- For simple 2-3 hop queries, SQL is acceptable
- For social graphs (6 degrees), dedicated graph DB is mandatory

---

## Problem 44: Gaps and Islands - Employee Attendance Streaks

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Find the longest streak of consecutive days each employee was present.

```sql
WITH attendance_islands AS (
    SELECT employee_id, attendance_date,
           attendance_date - (ROW_NUMBER() OVER (
               PARTITION BY employee_id ORDER BY attendance_date
           ))::INT AS island_id
    FROM Attendance
    WHERE status = 'present'
)
SELECT employee_id,
       MIN(attendance_date) AS streak_start,
       MAX(attendance_date) AS streak_end,
       COUNT(*) AS streak_length
FROM attendance_islands
GROUP BY employee_id, island_id
ORDER BY streak_length DESC;
```

**Find Current Active Streak:**
```sql
WITH ranked AS (
    SELECT employee_id, attendance_date, status,
           attendance_date - (ROW_NUMBER() OVER (
               PARTITION BY employee_id, status ORDER BY attendance_date
           ) * INTERVAL '1 day') AS grp
    FROM Attendance
    WHERE attendance_date <= CURRENT_DATE
)
SELECT employee_id, COUNT(*) AS current_streak
FROM ranked
WHERE status = 'present'
  AND grp = (
      SELECT grp FROM ranked r2 
      WHERE r2.employee_id = ranked.employee_id 
        AND r2.attendance_date = CURRENT_DATE
        AND r2.status = 'present'
      LIMIT 1
  )
GROUP BY employee_id;
```

---

## Problem 45: Window Function - Running Distinct Count

**Difficulty:** Hard | **Frequency:** Medium

**Problem:** Calculate running count of distinct users who have visited by each date.

```sql
-- Running distinct count (cumulative unique users)
WITH first_visits AS (
    SELECT user_id, MIN(visit_date) AS first_visit_date
    FROM PageVisits
    GROUP BY user_id
)
SELECT visit_date,
       SUM(COUNT(*)) OVER (ORDER BY first_visit_date) AS cumulative_unique_users
FROM first_visits
GROUP BY first_visit_date
ORDER BY first_visit_date;
```

**Alternative with dense approach:**
```sql
SELECT DISTINCT visit_date,
       COUNT(DISTINCT user_id) OVER (
           ORDER BY visit_date
           RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_unique_users
FROM PageVisits;
-- NOTE: COUNT(DISTINCT) in window functions is NOT supported in most DBs!
```

**Workaround for databases without window DISTINCT:**
```sql
WITH daily_new AS (
    SELECT MIN(visit_date) AS first_date, user_id
    FROM PageVisits
    GROUP BY user_id
),
daily_counts AS (
    SELECT first_date, COUNT(*) AS new_users
    FROM daily_new
    GROUP BY first_date
)
SELECT first_date AS date,
       SUM(new_users) OVER (ORDER BY first_date) AS cumulative_users
FROM daily_counts;
```

---

## Problem 46: LEAD/LAG for Detecting State Changes

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Find when order status changed and calculate time between states.

```sql
CREATE TABLE OrderStatusHistory (
    order_id INT,
    status VARCHAR(50),
    changed_at TIMESTAMP
);
```

**Solution:**
```sql
SELECT order_id, status, changed_at,
       LAG(status) OVER (PARTITION BY order_id ORDER BY changed_at) AS prev_status,
       LEAD(status) OVER (PARTITION BY order_id ORDER BY changed_at) AS next_status,
       changed_at - LAG(changed_at) OVER (PARTITION BY order_id ORDER BY changed_at) AS time_in_prev_state,
       LEAD(changed_at) OVER (PARTITION BY order_id ORDER BY changed_at) - changed_at AS time_in_current_state
FROM OrderStatusHistory
ORDER BY order_id, changed_at;
```

**Average Time in Each State:**
```sql
WITH state_durations AS (
    SELECT order_id, status,
           LEAD(changed_at) OVER (PARTITION BY order_id ORDER BY changed_at) - changed_at AS duration
    FROM OrderStatusHistory
)
SELECT status,
       AVG(duration) AS avg_duration,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration) AS median_duration,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration) AS p95_duration
FROM state_durations
WHERE duration IS NOT NULL
GROUP BY status;
```

---

## Problem 47: Correlated Subquery vs JOIN Performance

**Difficulty:** Medium | **Frequency:** High (Performance interviews)

**Problem:** Find employees whose salary is above their department average.

**Correlated Subquery (slower for large datasets):**
```sql
SELECT name, salary, department_id
FROM Employees e
WHERE salary > (
    SELECT AVG(salary) FROM Employees WHERE department_id = e.department_id
);
```

**JOIN approach (single scan):**
```sql
SELECT e.name, e.salary, e.department_id
FROM Employees e
JOIN (
    SELECT department_id, AVG(salary) AS avg_salary
    FROM Employees
    GROUP BY department_id
) dept_avg ON e.department_id = dept_avg.department_id
WHERE e.salary > dept_avg.avg_salary;
```

**Window Function (most elegant):**
```sql
SELECT name, salary, department_id
FROM (
    SELECT name, salary, department_id,
           AVG(salary) OVER (PARTITION BY department_id) AS dept_avg
    FROM Employees
) t
WHERE salary > dept_avg;
```

**Performance Analysis:**
- Correlated subquery: Executes inner query once per outer row → O(n × m)
- JOIN: Two scans + hash join → O(n + m)
- Window function: Single scan → O(n)
- Modern optimizers may decorrelate subqueries automatically

---

## Problem 48: JSON Querying in SQL

**Difficulty:** Medium | **Frequency:** High (Modern applications)

**Problem:** Query JSON data stored in PostgreSQL/MySQL columns.

```sql
CREATE TABLE Events (
    id INT,
    payload JSONB  -- PostgreSQL
);
```

**PostgreSQL JSONB Queries:**
```sql
-- Extract nested value
SELECT payload->>'user_id' AS user_id,
       payload->'metadata'->>'source' AS source,
       (payload->>'amount')::numeric AS amount
FROM Events
WHERE payload->>'event_type' = 'purchase'
  AND (payload->>'amount')::numeric > 100;

-- Query array elements
SELECT id, elem->>'product_id' AS product_id
FROM Events,
     jsonb_array_elements(payload->'items') AS elem
WHERE payload->>'event_type' = 'checkout';

-- Aggregate JSON
SELECT payload->>'category' AS category,
       COUNT(*),
       SUM((payload->>'amount')::numeric) AS total
FROM Events
GROUP BY payload->>'category';
```

**Index on JSON (GIN index):**
```sql
CREATE INDEX idx_events_payload ON Events USING GIN (payload);
CREATE INDEX idx_events_type ON Events ((payload->>'event_type'));
```

**MySQL JSON:**
```sql
SELECT JSON_EXTRACT(payload, '$.user_id') AS user_id,
       JSON_EXTRACT(payload, '$.metadata.source') AS source
FROM Events
WHERE JSON_EXTRACT(payload, '$.event_type') = 'purchase';
```

---

## Problem 49: Temporal Validity (Bi-Temporal Data)

**Difficulty:** Expert | **Frequency:** High (Finance, Compliance)

**Problem:** Track both business time (when something was true) and system time (when we recorded it).

```sql
CREATE TABLE ProductPrices (
    product_id INT,
    price DECIMAL(10,2),
    valid_from DATE,        -- Business time start
    valid_to DATE,          -- Business time end
    recorded_at TIMESTAMP,  -- System time (when recorded)
    superseded_at TIMESTAMP -- System time (when replaced)
);
```

**Find current price:**
```sql
SELECT product_id, price
FROM ProductPrices
WHERE product_id = 42
  AND CURRENT_DATE BETWEEN valid_from AND valid_to  -- Business time
  AND superseded_at IS NULL;  -- System time (current version)
```

**Find price as known on a specific date (point-in-time query):**
```sql
-- What did we think the price was on 2024-03-15?
SELECT product_id, price, valid_from, valid_to
FROM ProductPrices
WHERE product_id = 42
  AND recorded_at <= '2024-03-15'
  AND (superseded_at IS NULL OR superseded_at > '2024-03-15')
  AND '2024-03-15' BETWEEN valid_from AND valid_to;
```

**SQL:2011 Temporal Tables (supported in MariaDB, DB2):**
```sql
CREATE TABLE ProductPrices (
    product_id INT,
    price DECIMAL(10,2),
    valid_from DATE,
    valid_to DATE,
    PERIOD FOR business_time (valid_from, valid_to)
) WITH SYSTEM VERSIONING;

-- Query at a point in time
SELECT * FROM ProductPrices
FOR SYSTEM_TIME AS OF '2024-03-15'
WHERE product_id = 42;
```

---

## Problem 50: Advanced Set Operations - Exactly N of M Conditions

**Difficulty:** Hard | **Frequency:** Medium

**Problem:** Find users who have used exactly 3 out of 5 specific features.

```sql
WITH feature_usage AS (
    SELECT user_id,
           SUM(CASE WHEN feature = 'search' THEN 1 ELSE 0 END) AS used_search,
           SUM(CASE WHEN feature = 'export' THEN 1 ELSE 0 END) AS used_export,
           SUM(CASE WHEN feature = 'import' THEN 1 ELSE 0 END) AS used_import,
           SUM(CASE WHEN feature = 'share' THEN 1 ELSE 0 END) AS used_share,
           SUM(CASE WHEN feature = 'archive' THEN 1 ELSE 0 END) AS used_archive
    FROM FeatureEvents
    WHERE feature IN ('search', 'export', 'import', 'share', 'archive')
    GROUP BY user_id
)
SELECT user_id,
       (SIGN(used_search) + SIGN(used_export) + SIGN(used_import) + 
        SIGN(used_share) + SIGN(used_archive)) AS features_used
FROM feature_usage
HAVING features_used = 3;
```

**Elegant approach with COUNT DISTINCT:**
```sql
SELECT user_id
FROM FeatureEvents
WHERE feature IN ('search', 'export', 'import', 'share', 'archive')
GROUP BY user_id
HAVING COUNT(DISTINCT feature) = 3;
```

---

## Key Advanced Patterns Summary

| Pattern | Problems | When to Use |
|---------|----------|-------------|
| Recursive CTE | 29, 30, 32, 38, 43 | Hierarchies, graphs, sequence generation |
| Gaps & Islands | 27, 44 | Sessionization, streaks, consecutive detection |
| LATERAL JOIN | 41 | Top-N per group efficiently |
| Window Frames | 26, 42 | Moving averages, time-weighted calculations |
| JSON Querying | 48 | Semi-structured data in RDBMS |
| Temporal Queries | 49 | Audit, compliance, point-in-time |
| GROUPING SETS | 39 | Multi-dimensional reporting |
| Pattern Matching | 34 | Sequence detection in time-series |
