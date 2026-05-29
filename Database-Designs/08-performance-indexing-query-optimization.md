# Performance, Indexing & Query Optimization (Problems 151-170)

## Staff Architect Level - Making Queries Fast at Scale

---

## Problem 151: Index Design Fundamentals — When Indexes Help and Hurt

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Given this table with 100M rows, design optimal indexes:

```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(10,2),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);
```

**Common Queries and Their Ideal Indexes:**

```sql
-- Query 1: Orders by user (recent first)
SELECT * FROM orders WHERE user_id = @uid ORDER BY created_at DESC LIMIT 20;
-- Index: CREATE INDEX idx_user_created ON orders(user_id, created_at DESC);
-- WHY: Composite covers both filter + sort. DESC matches ORDER BY.

-- Query 2: Pending orders older than 24 hours
SELECT * FROM orders WHERE status = 'pending' AND created_at < NOW() - INTERVAL '24 hours';
-- Index: CREATE INDEX idx_status_created ON orders(status, created_at);
-- WHY: status first (equality), then created_at (range scan)

-- Query 3: Count orders by status
SELECT status, COUNT(*) FROM orders GROUP BY status;
-- Index: CREATE INDEX idx_status ON orders(status);
-- Or covering index: CREATE INDEX idx_status_covering ON orders(status) INCLUDE (order_id);

-- Query 4: Total revenue per user
SELECT user_id, SUM(total_amount) FROM orders GROUP BY user_id;
-- Index: CREATE INDEX idx_user_amount ON orders(user_id, total_amount);
-- WHY: Index-only scan — no table access needed
```

**The Equality-Range-Sort-Distinct Rule (ERS):**
```
Index column order should be:
1. Equality conditions first (WHERE x = ?)
2. Range conditions or Sort columns next (WHERE x > ? or ORDER BY x)
3. INCLUDE remaining projected columns for covering index

Example: WHERE status = 'active' AND created_at > '2024-01-01' ORDER BY total_amount
Index: (status, created_at, total_amount)
       ^^^^^^^^  ^^^^^^^^^^^  ^^^^^^^^^^^^
       Equality  Range        Sort (only works if range is satisfied)
```

**When Indexes HURT:**
- Tables with < 1000 rows (full scan is faster)
- Columns with very low cardinality (status with 3 values) on large tables
  - Exception: If you're filtering for rare value (0.1% of rows)
- Write-heavy tables (each INSERT/UPDATE must update all indexes)
- Expressions in WHERE clause that don't match the index

---

## Problem 152: Covering Indexes (Index-Only Scans)

**Difficulty:** Medium | **Frequency:** Very High

**Problem:** Eliminate table lookups by including all needed columns in the index.

```sql
-- Query: Get user email and name for active users
SELECT email, name FROM users WHERE status = 'active' AND created_at > '2024-01-01';

-- Without covering index:
-- 1. Index scan on (status, created_at) → get row pointers
-- 2. For EACH row, fetch from heap (random I/O!) → get email, name

-- With covering index (PostgreSQL INCLUDE):
CREATE INDEX idx_active_users_covering 
ON users(status, created_at) 
INCLUDE (email, name);
-- 1. Index-only scan → all data from index, zero heap fetches!

-- MySQL equivalent:
CREATE INDEX idx_active_users_covering 
ON users(status, created_at, email, name);
-- In MySQL, all columns must be in the index key (no INCLUDE)
```

**Verify Index-Only Scan:**
```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT email, name FROM users WHERE status = 'active' AND created_at > '2024-01-01';
-- Look for: "Index Only Scan" and "Heap Fetches: 0"
```

**Trade-off:** Wider indexes = more storage + slower writes. Only add INCLUDE columns for hot queries.

---

## Problem 153: Partial Indexes (Filtered Indexes)

**Difficulty:** Medium | **Frequency:** High

**Problem:** 95% of orders are 'completed'. You only query 'pending' (5%). A full index wastes space.

```sql
-- Partial index: Only index the rows you actually query
CREATE INDEX idx_pending_orders 
ON orders(created_at) 
WHERE status = 'pending';

-- This index is:
-- 1. 20x smaller than indexing all orders
-- 2. 20x faster to scan
-- 3. Less write overhead (only updates when status = 'pending')

-- Query MUST include the WHERE clause of the partial index:
SELECT * FROM orders WHERE status = 'pending' AND created_at < NOW() - INTERVAL '1 hour';
-- ✅ Uses idx_pending_orders

SELECT * FROM orders WHERE created_at < NOW() - INTERVAL '1 hour';
-- ❌ Cannot use idx_pending_orders (missing status = 'pending')
```

**Use Cases for Partial Indexes:**
```sql
-- Only index non-null values
CREATE INDEX idx_shipping ON orders(shipping_tracking_number) 
WHERE shipping_tracking_number IS NOT NULL;

-- Only index active users (exclude deleted)
CREATE INDEX idx_active_email ON users(email) WHERE deleted_at IS NULL;

-- Only index unprocessed items
CREATE INDEX idx_unprocessed ON events(created_at) WHERE processed_at IS NULL;
```

---

## Problem 154: Expression Indexes (Functional Indexes)

**Difficulty:** Medium | **Frequency:** High

**Problem:** Query uses a function on column, making regular index useless.

```sql
-- This query CANNOT use an index on email:
SELECT * FROM users WHERE LOWER(email) = 'john@example.com';
-- WHY: Index on `email` stores 'John@Example.com', but query looks for 'john@example.com'

-- Solution: Expression index
CREATE INDEX idx_email_lower ON users(LOWER(email));

-- Now this works:
SELECT * FROM users WHERE LOWER(email) = 'john@example.com';
-- ✅ Uses idx_email_lower

-- Other examples:
CREATE INDEX idx_year ON events(EXTRACT(YEAR FROM created_at));
CREATE INDEX idx_json_type ON events((payload->>'event_type'));
CREATE INDEX idx_date ON orders(DATE(created_at));
```

---

## Problem 155: Composite Index Column Order Matters

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Given index `(A, B, C)`, which queries can use it?

```sql
CREATE INDEX idx_abc ON table(A, B, C);

-- ✅ Uses index (leftmost prefix):
WHERE A = 1
WHERE A = 1 AND B = 2
WHERE A = 1 AND B = 2 AND C = 3
WHERE A = 1 AND B > 5
WHERE A = 1 ORDER BY B

-- ❌ Cannot use index (skips leftmost columns):
WHERE B = 2                  -- Skips A
WHERE C = 3                  -- Skips A, B
WHERE B = 2 AND C = 3       -- Skips A

-- ⚠️ Partially uses index:
WHERE A = 1 AND C = 3       -- Uses A, but cannot use C (gap at B)
WHERE A > 1 AND B = 2       -- Range on A prevents using B for equality
```

**Index Skip Scan (PostgreSQL 13+, MySQL 8.0.13+):**
```sql
-- Modern optimizers can sometimes "skip" leading columns
-- But it's still better to design indexes matching your queries
```

---

## Problem 156: EXPLAIN Plan Reading (Interview Skill)

**Difficulty:** Hard | **Frequency:** Very High

**Common Operations and Their Costs:**

```
Operation              | What it Means                    | Speed
-----------------------|----------------------------------|--------
Seq Scan               | Full table scan (reads ALL rows) | Slow for large tables
Index Scan             | Uses index, then fetches from heap | Good
Index Only Scan        | All data from index alone        | Best
Bitmap Index Scan      | Builds bitmap, then heap scan    | Good for many rows
Nested Loop            | For each outer row, scan inner   | Fast for small sets
Hash Join              | Build hash table, probe          | Fast for equi-joins
Merge Join             | Both sorted, merge together      | Fast for pre-sorted
Sort                   | In-memory or disk sort           | Check if spills to disk
Aggregate              | GROUP BY / COUNT / SUM           | Depends on input size
Materialize            | Stores sub-result in memory      | May spill to disk
```

**Example EXPLAIN Analysis:**
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, COUNT(o.order_id)
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.user_id, u.name
ORDER BY COUNT(o.order_id) DESC
LIMIT 10;
```

```
Limit (cost=1234.56..1234.89 rows=10)
  -> Sort (cost=1234.56..1267.89 rows=5000)
       Sort Key: (count(o.order_id)) DESC
       Sort Method: top-N heapsort  Memory: 25kB
    -> HashAggregate (cost=1100.00..1200.00 rows=5000)
         Group Key: u.user_id
      -> Hash Right Join (cost=100.00..900.00 rows=50000)
             Hash Cond: (o.user_id = u.user_id)
           -> Seq Scan on orders o (cost=0..500.00 rows=100000)
           -> Hash (cost=80.00..80.00 rows=5000)
                -> Index Scan on users u (cost=0..80.00 rows=5000)
                      Filter: (created_at > '2024-01-01')
```

**Red Flags to Look For:**
1. `Seq Scan` on large table where filter is selective
2. `Sort Method: external merge` (spilling to disk)
3. `Rows Removed by Filter: 999900` (scanned 1M, kept 100)
4. Nested Loop with large inner table (should be Hash Join)
5. `actual rows` >> `estimated rows` (stale statistics)

---

## Problem 157: Query Optimization — Rewriting Slow Queries

**Difficulty:** Hard | **Frequency:** Very High

**Problem 1: OR conditions preventing index usage**
```sql
-- SLOW: OR prevents single index usage
SELECT * FROM orders WHERE user_id = @uid OR email = @email;

-- FAST: UNION of two indexed queries
SELECT * FROM orders WHERE user_id = @uid
UNION
SELECT * FROM orders WHERE email = @email;
```

**Problem 2: Correlated subquery → JOIN**
```sql
-- SLOW: Executes subquery once per row
SELECT * FROM orders o
WHERE (SELECT MAX(amount) FROM order_items oi WHERE oi.order_id = o.order_id) > 1000;

-- FAST: JOIN with aggregate
SELECT o.* FROM orders o
JOIN (SELECT order_id, MAX(amount) AS max_amount FROM order_items GROUP BY order_id) oi
  ON o.order_id = oi.order_id
WHERE oi.max_amount > 1000;
```

**Problem 3: LIKE with leading wildcard**
```sql
-- SLOW: Cannot use B-tree index
SELECT * FROM products WHERE name LIKE '%phone%';

-- Options:
-- 1. Full-text search (PostgreSQL)
SELECT * FROM products WHERE to_tsvector('english', name) @@ to_tsquery('phone');
-- 2. Trigram index (pg_trgm)
CREATE INDEX idx_name_trgm ON products USING gin (name gin_trgm_ops);
-- 3. Elasticsearch for complex search
```

**Problem 4: COUNT(*) on large tables**
```sql
-- SLOW: Full table scan for exact count
SELECT COUNT(*) FROM events;  -- 500M rows → 30 seconds

-- FAST: Approximate count
SELECT reltuples::bigint FROM pg_class WHERE relname = 'events';
-- Or for filtered counts:
SELECT n_live_tup FROM pg_stat_user_tables WHERE relname = 'events';

-- Alternative: Maintain counter table
CREATE TABLE entity_counts (entity VARCHAR PRIMARY KEY, count BIGINT);
-- Update via trigger or application logic
```

---

## Problem 158: Pagination at Scale

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** `OFFSET 1000000 LIMIT 20` scans 1,000,020 rows and discards 1,000,000.

**Solution 1: Cursor-Based Pagination (Keyset)**
```sql
-- Instead of OFFSET, use WHERE clause on the last seen value
-- First page:
SELECT order_id, created_at, total_amount
FROM orders
WHERE user_id = @uid
ORDER BY created_at DESC, order_id DESC
LIMIT 20;

-- Next page (using last row's values as cursor):
SELECT order_id, created_at, total_amount
FROM orders
WHERE user_id = @uid
  AND (created_at, order_id) < (@last_created_at, @last_order_id)
ORDER BY created_at DESC, order_id DESC
LIMIT 20;
```

**Why Cursor > OFFSET:**
- OFFSET 1M: Scans 1M rows, takes seconds
- Cursor: Uses index, instant regardless of page number
- Downside: No "jump to page 50" — only next/previous

**Solution 2: Deferred JOIN (for complex queries)**
```sql
-- SLOW: Fetches all columns for 1M rows before limiting
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 1000000;

-- FAST: Get IDs first (index-only), then fetch full rows
SELECT o.* FROM orders o
JOIN (
    SELECT order_id FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 1000000
) ids ON o.order_id = ids.order_id;
```

---

## Problem 159: Partitioning Strategies

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Table has 2B rows, queries are slow, vacuuming takes hours.

**Range Partitioning (by date — most common):**
```sql
CREATE TABLE events (
    event_id BIGINT,
    user_id UUID,
    event_type VARCHAR(50),
    payload JSONB,
    created_at TIMESTAMP NOT NULL
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... auto-generate with pg_partman

-- Benefits:
-- 1. Queries with date filter only scan relevant partitions (partition pruning)
-- 2. DROP partition is instant (vs DELETE which generates WAL)
-- 3. VACUUM runs per-partition (smaller units)
-- 4. Can have different storage (old partitions on cold storage)
```

**List Partitioning (by region/tenant):**
```sql
CREATE TABLE orders (
    order_id UUID,
    region VARCHAR(10),
    total DECIMAL(10,2),
    created_at TIMESTAMP
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('EU');
CREATE TABLE orders_apac PARTITION OF orders FOR VALUES IN ('APAC');
```

**Hash Partitioning (even distribution):**
```sql
CREATE TABLE sessions (
    session_id UUID,
    user_id UUID,
    data JSONB
) PARTITION BY HASH (session_id);

CREATE TABLE sessions_0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

---

## Problem 160: Materialized Views for Complex Aggregations

**Difficulty:** Medium | **Frequency:** High

```sql
-- Dashboard showing daily metrics (expensive to compute live)
CREATE MATERIALIZED VIEW daily_metrics AS
SELECT 
    DATE(created_at) AS metric_date,
    COUNT(*) AS total_orders,
    COUNT(DISTINCT user_id) AS unique_customers,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_amount) AS median_order
FROM orders
WHERE status = 'completed'
GROUP BY DATE(created_at)
WITH DATA;

-- Create index on the materialized view
CREATE UNIQUE INDEX idx_daily_metrics_date ON daily_metrics(metric_date);

-- Refresh (can be done concurrently to avoid locking)
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_metrics;
-- CONCURRENTLY requires a UNIQUE index, doesn't lock during refresh
```

**Refresh Strategies:**
| Strategy | Freshness | Implementation |
|----------|-----------|----------------|
| Scheduled (cron) | Minutes to hours | `REFRESH` every 5 min |
| On-demand | On query if stale | Application checks `last_refresh` |
| Trigger-based | Near real-time | Trigger on source table changes |
| Incremental | Real-time | Custom logic with diff tables |

---

## Problem 161: Denormalization Patterns for Read Performance

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Join of 5 tables for product page takes 200ms. Need < 10ms.

**Strategy 1: Pre-computed columns**
```sql
-- Instead of JOINing to calculate order total:
ALTER TABLE orders ADD COLUMN item_count INT DEFAULT 0;
ALTER TABLE orders ADD COLUMN total_amount DECIMAL(10,2) DEFAULT 0;
-- Update via trigger on order_items changes
```

**Strategy 2: JSON aggregation column**
```sql
-- Store related data as JSON to avoid JOINs
ALTER TABLE products ADD COLUMN rating_summary JSONB;
-- Updated async: {"avg": 4.5, "count": 123, "distribution": [5, 10, 20, 40, 48]}

ALTER TABLE orders ADD COLUMN items_snapshot JSONB;
-- Store order items at order time (don't reference current product data)
```

**Strategy 3: Read-optimized tables (CQRS)**
```sql
-- Separate read model, updated by events
CREATE TABLE product_read_model (
    product_id UUID PRIMARY KEY,
    title VARCHAR(500),
    price DECIMAL(10,2),
    seller_name VARCHAR(255),
    category_path VARCHAR(500),
    average_rating DECIMAL(3,2),
    review_count INT,
    in_stock BOOLEAN,
    primary_image_url VARCHAR(500),
    -- All data needed for product listing in one row, zero JOINs
    updated_at TIMESTAMP
);
```

---

## Problem 162: Index Maintenance and Bloat

**Difficulty:** Hard | **Frequency:** High (Operations)

```sql
-- Check index bloat (PostgreSQL)
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
       idx_scan AS times_used,
       idx_tup_read,
       idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

-- Find unused indexes (waste of write resources)
SELECT schemaname, tablename, indexname, 
       pg_size_pretty(pg_relation_size(indexrelid)) AS size,
       idx_scan AS scans
FROM pg_stat_user_indexes
WHERE idx_scan = 0  -- Never used since last stats reset
  AND indexrelid NOT IN (SELECT conindid FROM pg_constraint)  -- Not a constraint
ORDER BY pg_relation_size(indexrelid) DESC;

-- Find duplicate indexes
SELECT pg_size_pretty(sum(pg_relation_size(idx))::bigint) as size,
       (array_agg(idx))[1] as idx1, (array_agg(idx))[2] as idx2,
       (array_agg(idx))[3] as idx3
FROM (
    SELECT indexrelid::regclass as idx, 
           (indrelid::text || E'\n' || indclass::text || E'\n' || 
            indkey::text || E'\n' || coalesce(indexprs::text,'') || 
            E'\n' || coalesce(indpred::text,'')) as key
    FROM pg_index
) sub
GROUP BY key HAVING count(*) > 1
ORDER BY sum(pg_relation_size(idx)) DESC;

-- REINDEX to fix bloated indexes (online in PostgreSQL 12+)
REINDEX INDEX CONCURRENTLY idx_orders_user_id;
```

---

## Problem 163: Query Plan Caching and Prepared Statements

**Difficulty:** Hard | **Frequency:** High

```sql
-- PostgreSQL: Prepared statements cache query plans
PREPARE get_user_orders AS
SELECT * FROM orders WHERE user_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT $3;

EXECUTE get_user_orders('user-123', 'pending', 20);

-- Problem: Generic plan may be suboptimal for skewed data
-- Force custom plan:
SET plan_cache_mode = 'force_custom_plan';

-- Check if cached plan is being used:
SELECT * FROM pg_prepared_statements;
```

**The Parameterized Query Dilemma:**
```sql
-- With parameter: Optimizer can't know the value → generic plan
WHERE status = $1  -- If status has 3 values with 90/5/5 distribution, generic plan may be wrong

-- Without parameter: Perfect plan, but SQL injection risk + plan cache bloat
WHERE status = 'pending'  -- Optimizer knows only 5% of rows match → chooses index

-- Solution: Use pg_hint_plan or dynamic SQL for critical queries with skewed data
```

---

## Problem 164: Optimizing COUNT Queries

**Difficulty:** Medium | **Frequency:** Very High

```sql
-- Problem: SELECT COUNT(*) FROM large_table is always slow in PostgreSQL
-- (No cached row count like MySQL's InnoDB)

-- Solution 1: Approximate count (for UI "showing ~1.2M results")
SELECT reltuples::bigint AS approximate_count
FROM pg_class WHERE relname = 'orders';

-- Solution 2: Counter cache table
CREATE TABLE table_counts (
    table_name VARCHAR(100) PRIMARY KEY,
    row_count BIGINT NOT NULL DEFAULT 0
);
-- Maintain via triggers:
CREATE TRIGGER orders_count_trigger AFTER INSERT OR DELETE ON orders
FOR EACH ROW EXECUTE FUNCTION update_count();

-- Solution 3: HyperLogLog for distinct counts
-- PostgreSQL extension: postgresql-hll
CREATE EXTENSION hll;
SELECT hll_cardinality(hll_union_agg(hll_add(hll_empty(), hll_hash_text(user_id::text))))
FROM events;
-- Approximate distinct count with ~2% error, constant memory

-- Solution 4: For filtered counts, use partial index + index-only scan
CREATE INDEX idx_pending_count ON orders(order_id) WHERE status = 'pending';
SELECT COUNT(*) FROM orders WHERE status = 'pending';
-- Scans small partial index instead of full table
```

---

## Problem 165: Hot Spot Prevention (Single-Row Contention)

**Difficulty:** Expert | **Frequency:** High

**Problem:** Counter table updated by every request creates lock contention.

```sql
-- SLOW: All requests fight for same row lock
UPDATE counters SET value = value + 1 WHERE name = 'page_views';

-- Solution 1: Sharded counters
CREATE TABLE sharded_counters (
    name VARCHAR(100),
    shard_id INT,  -- 0 to 15 (16 shards)
    value BIGINT DEFAULT 0,
    PRIMARY KEY (name, shard_id)
);

-- Write: Random shard (distributes contention)
UPDATE sharded_counters 
SET value = value + 1
WHERE name = 'page_views' AND shard_id = (RANDOM() * 15)::int;

-- Read: Sum all shards
SELECT SUM(value) FROM sharded_counters WHERE name = 'page_views';

-- Solution 2: Batch updates (buffer in Redis, flush periodically)
-- Accumulate in Redis INCR, flush to SQL every 5 seconds

-- Solution 3: Append-only log + periodic aggregation
INSERT INTO counter_events (name, delta) VALUES ('page_views', 1);
-- Background job sums and updates materialized counter
```

---

## Problem 166: GIN and GiST Index Types

**Difficulty:** Hard | **Frequency:** High

```sql
-- GIN (Generalized Inverted Index): Best for containment queries
-- Use for: Full-text search, JSONB, arrays, trigrams

-- Full-text search
CREATE INDEX idx_search ON articles USING GIN (to_tsvector('english', title || ' ' || body));
SELECT * FROM articles WHERE to_tsvector('english', title || ' ' || body) @@ to_tsquery('database & design');

-- JSONB containment
CREATE INDEX idx_payload ON events USING GIN (payload jsonb_path_ops);
SELECT * FROM events WHERE payload @> '{"event_type": "purchase"}';

-- Array contains
CREATE INDEX idx_tags ON posts USING GIN (tags);
SELECT * FROM posts WHERE tags @> ARRAY['postgresql', 'performance'];

-- Trigram (for LIKE '%partial%' queries)
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_name_trgm ON products USING GIN (name gin_trgm_ops);
SELECT * FROM products WHERE name LIKE '%phone%';  -- Now uses index!


-- GiST (Generalized Search Tree): Best for spatial/range/nearest-neighbor
-- Use for: PostGIS geometry, range types, full-text (ranking), exclusion constraints

-- Spatial query
CREATE INDEX idx_location ON venues USING GiST (location);
SELECT * FROM venues WHERE ST_DWithin(location, ST_MakePoint(-73.99, 40.73)::geography, 5000);

-- Range overlap (booking systems!)
CREATE INDEX idx_booking_range ON bookings USING GiST (tstzrange(start_time, end_time));
-- Used by exclusion constraints to prevent double-booking

-- Nearest neighbor
SELECT * FROM places ORDER BY location <-> ST_MakePoint(@lng, @lat)::geography LIMIT 10;
```

---

## Problem 167: Connection Between Indexes and Sort Operations

**Difficulty:** Hard | **Frequency:** High

```sql
-- If ORDER BY matches index order, no sort needed!
CREATE INDEX idx_orders_date ON orders(created_at DESC);

-- ✅ No sort (index delivers rows in order):
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20;
-- Plan: Index Scan Backward → no Sort node

-- ❌ Sort required (index doesn't match):
SELECT * FROM orders ORDER BY total_amount DESC LIMIT 20;
-- Plan: Seq Scan → Sort → Limit

-- Composite index for covering filter + sort:
CREATE INDEX idx_user_date ON orders(user_id, created_at DESC);
-- ✅ No sort:
SELECT * FROM orders WHERE user_id = @uid ORDER BY created_at DESC;

-- ⚠️ Mixed sort directions:
CREATE INDEX idx_mixed ON products(category ASC, price DESC);
-- ✅ Matches: ORDER BY category ASC, price DESC
-- ❌ Doesn't match: ORDER BY category ASC, price ASC
```

---

## Problem 168: Analyzing and Fixing N+1 Query Problems

**Difficulty:** Medium | **Frequency:** Very High (ORM-heavy applications)

**Problem:** Loading 100 orders and their items = 1 query for orders + 100 queries for items.

```sql
-- N+1 Pattern (BAD):
SELECT * FROM orders WHERE user_id = @uid;  -- Returns 100 orders
-- For EACH order:
SELECT * FROM order_items WHERE order_id = @oid;  -- 100 separate queries!

-- Fix 1: JOIN (single query)
SELECT o.*, oi.* FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.user_id = @uid;
-- Problem: Duplicates order data for each item

-- Fix 2: Two queries with IN clause
SELECT * FROM orders WHERE user_id = @uid;
SELECT * FROM order_items WHERE order_id IN (@id1, @id2, ..., @id100);
-- Application joins in memory. 2 queries total regardless of N.

-- Fix 3: Lateral join (PostgreSQL — get first 3 items per order)
SELECT o.*, items.*
FROM orders o
CROSS JOIN LATERAL (
    SELECT * FROM order_items oi 
    WHERE oi.order_id = o.order_id 
    ORDER BY oi.line_number LIMIT 3
) items
WHERE o.user_id = @uid;

-- Fix 4: Array aggregation (return items as JSON array)
SELECT o.order_id, o.total_amount,
       json_agg(json_build_object('item_id', oi.item_id, 'product', oi.product_name, 'qty', oi.quantity))
           AS items
FROM orders o
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.user_id = @uid
GROUP BY o.order_id;
```

---

## Problem 169: Statistics and Cardinality Estimation

**Difficulty:** Expert | **Frequency:** High (Performance tuning)

```sql
-- PostgreSQL stores statistics about data distribution
-- Optimizer uses these to estimate row counts and choose plans

-- View statistics:
SELECT attname, n_distinct, most_common_vals, most_common_freqs, histogram_bounds
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';

-- n_distinct: -0.5 means 50% unique, positive number = exact distinct count
-- most_common_vals: ['completed', 'pending', 'cancelled']
-- most_common_freqs: [0.85, 0.10, 0.05]
-- histogram_bounds: Distribution of non-MCV values

-- Force statistics refresh:
ANALYZE orders;

-- Increase statistics granularity for important columns:
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
-- Default is 100 histogram buckets; increase for skewed data
ANALYZE orders;

-- Extended statistics (cross-column correlation):
CREATE STATISTICS stat_orders_status_date (dependencies)
    ON status, created_at FROM orders;
ANALYZE orders;
-- Helps optimizer understand: 'pending' orders are mostly recent
```

---

## Problem 170: Benchmarking and Load Testing Database Queries

**Difficulty:** Hard | **Frequency:** High

**Tools and Techniques:**

```sql
-- 1. pg_stat_statements (top SQL by time/calls)
CREATE EXTENSION pg_stat_statements;

SELECT query, calls, total_exec_time, mean_exec_time,
       rows, shared_blks_hit, shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- 2. auto_explain (log slow queries with plans)
LOAD 'auto_explain';
SET auto_explain.log_min_duration = '100ms';
SET auto_explain.log_analyze = true;

-- 3. pg_stat_user_tables (table-level I/O)
SELECT relname, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch,
       n_tup_ins, n_tup_upd, n_tup_del,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC;

-- 4. Buffer cache hit ratio (should be > 99%)
SELECT 
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as hit_ratio
FROM pg_statio_user_tables;
```

**Load Testing:**
```bash
# pgbench (built-in PostgreSQL benchmark)
pgbench -c 50 -j 4 -T 60 -f custom_query.sql mydb
# -c 50: 50 concurrent connections
# -j 4: 4 threads
# -T 60: Run for 60 seconds

# sysbench (more flexible)
sysbench oltp_read_write --db-driver=pgsql --pgsql-db=mydb \
    --tables=10 --table-size=1000000 --threads=32 --time=300 run
```

---

## Performance Optimization Checklist

```
□ Are there indexes for all WHERE/JOIN/ORDER BY columns?
□ Are composite indexes in correct order (equality → range → sort)?
□ Are there covering indexes for hot queries?
□ Are partial indexes used for selective filters?
□ Is EXPLAIN showing Index Scan (not Seq Scan) for selective queries?
□ Are statistics up to date (ANALYZE recently)?
□ Is buffer cache hit ratio > 99%?
□ Are there unused indexes consuming write resources?
□ Is pagination using cursor-based (not OFFSET)?
□ Are N+1 queries eliminated?
□ Are expensive aggregations materialized?
□ Are tables partitioned if > 100M rows?
□ Are hot counters sharded?
□ Is connection pooling properly configured?
□ Are queries parameterized (prepared statements)?
```
