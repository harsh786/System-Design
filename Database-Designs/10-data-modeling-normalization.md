# Data Modeling & Normalization Problems (Problems 186-200)

## Staff Architect Level - Schema Design Theory, Anti-Patterns, Trade-offs

---

## Problem 186: Normalization Forms Deep Dive

**Difficulty:** Hard | **Frequency:** Very High (Fundamentals)

### First Normal Form (1NF): Atomic Values
```sql
-- VIOLATION: Repeating groups / multi-valued columns
CREATE TABLE orders_bad (
    order_id INT,
    customer_name VARCHAR(255),
    items VARCHAR(1000)  -- "iPhone,Case,Charger" — NOT 1NF!
);

-- FIX: Separate table for multi-valued attribute
CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL
);
CREATE TABLE order_items (
    order_id INT,
    item_id INT,
    product_name VARCHAR(255),
    PRIMARY KEY (order_id, item_id)
);
```

### Second Normal Form (2NF): No Partial Dependencies
```sql
-- VIOLATION: Non-key attribute depends on PART of composite key
CREATE TABLE order_items_bad (
    order_id INT,
    product_id INT,
    product_name VARCHAR(255),  -- Depends only on product_id, not full key!
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);

-- FIX: Move partial dependency to its own table
CREATE TABLE products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255)
);
CREATE TABLE order_items (
    order_id INT,
    product_id INT REFERENCES products(product_id),
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);
```

### Third Normal Form (3NF): No Transitive Dependencies
```sql
-- VIOLATION: Non-key attribute depends on another non-key attribute
CREATE TABLE employees_bad (
    emp_id INT PRIMARY KEY,
    emp_name VARCHAR(255),
    dept_id INT,
    dept_name VARCHAR(255),    -- Depends on dept_id, not emp_id!
    dept_location VARCHAR(255) -- Also depends on dept_id transitively
);

-- FIX: Remove transitive dependency
CREATE TABLE departments (
    dept_id INT PRIMARY KEY,
    dept_name VARCHAR(255),
    dept_location VARCHAR(255)
);
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    emp_name VARCHAR(255),
    dept_id INT REFERENCES departments(dept_id)
);
```

### Boyce-Codd Normal Form (BCNF): Every determinant is a candidate key
```sql
-- VIOLATION: Student can have only one advisor per subject
-- (student, subject) → advisor
-- advisor → subject (advisor teaches only one subject)
-- advisor is a determinant but NOT a candidate key

CREATE TABLE student_advisors_bad (
    student_id INT,
    subject VARCHAR(100),
    advisor VARCHAR(100),
    PRIMARY KEY (student_id, subject)
    -- advisor → subject violates BCNF
);

-- FIX: Decompose
CREATE TABLE advisors (
    advisor_id INT PRIMARY KEY,
    advisor_name VARCHAR(100),
    subject VARCHAR(100)
);
CREATE TABLE student_advisors (
    student_id INT,
    advisor_id INT REFERENCES advisors(advisor_id),
    PRIMARY KEY (student_id, advisor_id)
);
```

### When to STOP Normalizing:

| Situation | Normalize | Denormalize |
|-----------|-----------|-------------|
| OLTP (transactional) | Yes (3NF) | Selective for hot queries |
| OLAP (analytics) | No | Star/Snowflake schema |
| Microservices | Per-service optimal | Event-driven sync |
| Read-heavy API | 3NF source | Materialized read models |
| High-write throughput | Yes (fewer indexes) | Avoid computed columns |

---

## Problem 187: Star Schema vs Snowflake Schema (Data Warehousing)

**Difficulty:** Hard | **Frequency:** Very High (Analytics/BI interviews)

### Star Schema:
```sql
-- Fact table (center of star): Measures/metrics
CREATE TABLE fact_sales (
    sale_id BIGINT PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    product_key INT NOT NULL REFERENCES dim_product(product_key),
    store_key INT NOT NULL REFERENCES dim_store(store_key),
    customer_key INT NOT NULL REFERENCES dim_customer(customer_key),
    -- Measures
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    cost_amount DECIMAL(10,2)
);

-- Dimension tables (points of star): Descriptive attributes
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,  -- 20240315
    full_date DATE NOT NULL,
    day_of_week INT,
    day_name VARCHAR(10),
    month INT,
    month_name VARCHAR(10),
    quarter INT,
    year INT,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    fiscal_year INT,
    fiscal_quarter INT
);

CREATE TABLE dim_product (
    product_key INT PRIMARY KEY,
    product_id UUID,  -- Source system ID
    product_name VARCHAR(500),
    brand VARCHAR(255),
    category VARCHAR(255),
    subcategory VARCHAR(255),
    -- SCD Type 2 fields (slowly changing dimension)
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE TABLE dim_store (
    store_key INT PRIMARY KEY,
    store_id INT,
    store_name VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(50)
);

CREATE TABLE dim_customer (
    customer_key INT PRIMARY KEY,
    customer_id UUID,
    name VARCHAR(255),
    segment VARCHAR(50),  -- "Enterprise", "SMB", "Consumer"
    acquisition_channel VARCHAR(100),
    lifetime_value_tier VARCHAR(20)
);
```

### Snowflake Schema (Normalized dimensions):
```sql
-- Dimensions are further normalized
CREATE TABLE dim_product (
    product_key INT PRIMARY KEY,
    product_name VARCHAR(500),
    brand_key INT REFERENCES dim_brand(brand_key),
    subcategory_key INT REFERENCES dim_subcategory(subcategory_key)
);

CREATE TABLE dim_brand (
    brand_key INT PRIMARY KEY,
    brand_name VARCHAR(255),
    manufacturer VARCHAR(255)
);

CREATE TABLE dim_subcategory (
    subcategory_key INT PRIMARY KEY,
    subcategory_name VARCHAR(255),
    category_key INT REFERENCES dim_category(category_key)
);

CREATE TABLE dim_category (
    category_key INT PRIMARY KEY,
    category_name VARCHAR(255),
    department VARCHAR(100)
);
```

**Star vs Snowflake:**

| Aspect | Star | Snowflake |
|--------|------|-----------|
| Joins | Fewer (faster queries) | More (normalized) |
| Storage | More (denormalized dims) | Less |
| Query simplicity | Simpler | Complex |
| ETL complexity | More (denormalize dims) | Less |
| BI tool compatibility | Better | Acceptable |
| Best for | Most DW/BI use cases | Very large dimensions |

---

## Problem 188: Slowly Changing Dimensions (SCD)

**Difficulty:** Hard | **Frequency:** Very High (Data engineering)

**Problem:** A customer changes their address. How do you track historical vs current state?

### SCD Type 1: Overwrite (No History)
```sql
-- Just update the row. Previous value lost.
UPDATE dim_customer SET city = 'New York' WHERE customer_id = 123;
-- Use when: History doesn't matter (fixing typos)
```

### SCD Type 2: Add New Row (Full History)
```sql
CREATE TABLE dim_customer (
    customer_key INT PRIMARY KEY AUTO_INCREMENT,  -- Surrogate key
    customer_id INT NOT NULL,  -- Natural/business key
    name VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    -- SCD Type 2 tracking
    effective_from DATE NOT NULL,
    effective_to DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1
);

-- Customer moves from Boston to New York:
-- Step 1: Close current record
UPDATE dim_customer 
SET effective_to = CURRENT_DATE - 1, is_current = FALSE
WHERE customer_id = 123 AND is_current = TRUE;

-- Step 2: Insert new record
INSERT INTO dim_customer (customer_id, name, city, state, effective_from, is_current, version)
VALUES (123, 'John Doe', 'New York', 'NY', CURRENT_DATE, TRUE, 2);

-- Query current state:
SELECT * FROM dim_customer WHERE customer_id = 123 AND is_current = TRUE;

-- Query state at a point in time:
SELECT * FROM dim_customer 
WHERE customer_id = 123 AND '2023-06-15' BETWEEN effective_from AND effective_to;
```

### SCD Type 3: Add Column (Limited History)
```sql
CREATE TABLE dim_customer (
    customer_key INT PRIMARY KEY,
    customer_id INT NOT NULL,
    current_city VARCHAR(100),
    previous_city VARCHAR(100),
    city_changed_at DATE
);
-- Only tracks one previous value. Use when: Only need immediate prior state.
```

### SCD Type 4: History Table
```sql
CREATE TABLE dim_customer (
    customer_key INT PRIMARY KEY,
    customer_id INT,
    name VARCHAR(255),
    city VARCHAR(100)  -- Always current
);

CREATE TABLE dim_customer_history (
    history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_key INT NOT NULL,
    city VARCHAR(100),
    effective_from DATE,
    effective_to DATE
);
```

---

## Problem 189: Polymorphic Associations (Multi-Type Relationships)

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Comments can belong to Posts, Photos, or Videos. How to model?

### Approach 1: Separate Foreign Key Columns (Exclusive Arc)
```sql
CREATE TABLE comments (
    comment_id UUID PRIMARY KEY,
    content TEXT,
    user_id UUID,
    -- Exclusive arc — only ONE should be non-null
    post_id UUID REFERENCES posts(post_id),
    photo_id UUID REFERENCES photos(photo_id),
    video_id UUID REFERENCES videos(video_id),
    CHECK (
        (post_id IS NOT NULL)::int + 
        (photo_id IS NOT NULL)::int + 
        (video_id IS NOT NULL)::int = 1
    )
);
```
**Pros:** Referential integrity enforced. **Cons:** Adding new commentable types requires ALTER TABLE.

### Approach 2: Polymorphic columns (Rails-style)
```sql
CREATE TABLE comments (
    comment_id UUID PRIMARY KEY,
    content TEXT,
    user_id UUID,
    commentable_type VARCHAR(50) NOT NULL,  -- 'Post', 'Photo', 'Video'
    commentable_id UUID NOT NULL,
    INDEX idx_commentable (commentable_type, commentable_id)
);
```
**Pros:** Flexible, no schema changes. **Cons:** NO referential integrity! Can't enforce FK.

### Approach 3: Shared Parent Table (Inheritance)
```sql
CREATE TABLE commentable_entities (
    entity_id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL
);

CREATE TABLE posts (
    post_id UUID PRIMARY KEY REFERENCES commentable_entities(entity_id),
    title VARCHAR(500),
    body TEXT
);

CREATE TABLE photos (
    photo_id UUID PRIMARY KEY REFERENCES commentable_entities(entity_id),
    url VARCHAR(500)
);

CREATE TABLE comments (
    comment_id UUID PRIMARY KEY,
    entity_id UUID NOT NULL REFERENCES commentable_entities(entity_id),
    content TEXT,
    user_id UUID
);
```
**Pros:** Full referential integrity. **Cons:** Extra join + indirection.

### Approach 4: Separate Comment Tables
```sql
CREATE TABLE post_comments (
    comment_id UUID PRIMARY KEY,
    post_id UUID NOT NULL REFERENCES posts(post_id),
    content TEXT
);

CREATE TABLE photo_comments (
    comment_id UUID PRIMARY KEY,
    photo_id UUID NOT NULL REFERENCES photos(photo_id),
    content TEXT
);
```
**Pros:** Simple, full integrity. **Cons:** Code duplication, can't query "all comments by user" easily.

**Architect Recommendation:** Use Approach 3 (shared parent) for strict integrity, or Approach 2 (polymorphic) for flexibility with application-level validation.

---

## Problem 190: EAV (Entity-Attribute-Value) Pattern

**Difficulty:** Hard | **Frequency:** High

**Problem:** Different product types have completely different attributes (phones have screen_size, shoes have shoe_size).

```sql
-- EAV Schema
CREATE TABLE product_attributes (
    entity_id UUID NOT NULL REFERENCES products(product_id),
    attribute_name VARCHAR(100) NOT NULL,
    attribute_value TEXT,
    value_type VARCHAR(20),  -- 'string', 'number', 'boolean', 'date'
    PRIMARY KEY (entity_id, attribute_name)
);

-- Query: Find phones with screen > 6 inches
SELECT entity_id
FROM product_attributes
WHERE attribute_name = 'screen_size' 
  AND CAST(attribute_value AS DECIMAL) > 6.0
  AND entity_id IN (
      SELECT entity_id FROM product_attributes 
      WHERE attribute_name = 'category' AND attribute_value = 'phone'
  );
```

**Problems with EAV:**
1. No type safety (everything is TEXT)
2. No referential integrity on values
3. Complex queries (pivot needed for display)
4. Poor performance (many self-joins)
5. No constraint enforcement

**Better Alternative: JSONB Column**
```sql
CREATE TABLE products (
    product_id UUID PRIMARY KEY,
    name VARCHAR(500),
    category VARCHAR(100),
    attributes JSONB NOT NULL DEFAULT '{}'
);

-- Index for querying JSON
CREATE INDEX idx_attributes ON products USING GIN (attributes);

-- Query: Find phones with screen > 6
SELECT * FROM products
WHERE category = 'phone'
  AND (attributes->>'screen_size')::numeric > 6.0;
```

**When EAV is acceptable:**
- User-defined custom fields (CRM systems)
- Highly dynamic schemas that change weekly
- When you need to query by attribute name dynamically

---

## Problem 191: Soft Delete vs Hard Delete

**Difficulty:** Medium | **Frequency:** Very High

### Soft Delete:
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255),
    name VARCHAR(255),
    deleted_at TIMESTAMP,  -- NULL = active
    deleted_by UUID
);

-- "Delete" a user:
UPDATE users SET deleted_at = NOW(), deleted_by = @admin_id WHERE user_id = @uid;

-- All queries must filter:
SELECT * FROM users WHERE deleted_at IS NULL;

-- Partial index for performance:
CREATE INDEX idx_active_users ON users(email) WHERE deleted_at IS NULL;
```

### Hard Delete with Archive:
```sql
-- Move to archive table before deleting
INSERT INTO users_archive SELECT *, NOW() AS archived_at FROM users WHERE user_id = @uid;
DELETE FROM users WHERE user_id = @uid;
```

### Comparison:

| Aspect | Soft Delete | Hard Delete |
|--------|-------------|-------------|
| Recovery | Easy (update NULL) | Hard (restore from archive/backup) |
| Performance | Slower (table bloat) | Better (smaller table) |
| Complexity | Every query needs filter | Simple queries |
| GDPR | Still technically "stored" | True deletion |
| Unique constraints | Complex (email unique among active) | Simple |
| Foreign keys | No orphans | Must handle cascades |

**GDPR-compliant soft delete:**
```sql
-- Don't just mark as deleted — anonymize PII
UPDATE users 
SET email = CONCAT('deleted_', user_id, '@removed.com'),
    name = 'Deleted User',
    phone = NULL,
    address = NULL,
    deleted_at = NOW()
WHERE user_id = @uid;
```

---

## Problem 192: Audit Trail Design

**Difficulty:** Hard | **Frequency:** Very High (Compliance)

### Approach 1: Trigger-based audit
```sql
CREATE TABLE audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],
    changed_by UUID,
    changed_at TIMESTAMP DEFAULT NOW(),
    session_info JSONB  -- IP, user-agent, etc.
);

-- Generic audit trigger (PostgreSQL)
CREATE OR REPLACE FUNCTION audit_trigger_func() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, action, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id::text, 'INSERT', row_to_json(NEW)::jsonb, 
                current_setting('app.current_user', true)::uuid);
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values, new_values, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id::text, 'UPDATE', row_to_json(OLD)::jsonb, 
                row_to_json(NEW)::jsonb, current_setting('app.current_user', true)::uuid);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values, changed_by)
        VALUES (TG_TABLE_NAME, OLD.id::text, 'DELETE', row_to_json(OLD)::jsonb,
                current_setting('app.current_user', true)::uuid);
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply to any table:
CREATE TRIGGER users_audit AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
```

### Approach 2: Event Sourcing (source of truth is the log)
```sql
-- The event log IS the data. Current state is derived.
-- See Problem 148 for full implementation.
```

### Approach 3: Temporal Tables (SQL:2011)
```sql
-- MariaDB / SQL Server support system-versioned temporal tables
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    name VARCHAR(255),
    salary DECIMAL(10,2),
    valid_from DATETIME GENERATED ALWAYS AS ROW START,
    valid_to DATETIME GENERATED ALWAYS AS ROW END,
    PERIOD FOR SYSTEM_TIME (valid_from, valid_to)
) WITH SYSTEM VERSIONING;

-- Query historical state:
SELECT * FROM employees FOR SYSTEM_TIME AS OF '2023-06-15 10:00:00';
SELECT * FROM employees FOR SYSTEM_TIME BETWEEN '2023-01-01' AND '2023-12-31';
```

---

## Problem 193: Designing for Schema Evolution

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** How to change schema without breaking running applications (zero-downtime migrations)?

### Safe Operations (no lock / instant):
```sql
-- Adding a nullable column (instant in PG 11+)
ALTER TABLE orders ADD COLUMN notes TEXT;

-- Adding a column with non-volatile default (instant in PG 11+)
ALTER TABLE orders ADD COLUMN priority INT DEFAULT 0;

-- Creating an index concurrently (no lock)
CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);

-- Adding a CHECK constraint without validation
ALTER TABLE orders ADD CONSTRAINT chk_amount CHECK (amount > 0) NOT VALID;
```

### Unsafe Operations (require careful handling):
```sql
-- DANGEROUS: Adding NOT NULL without default (rewrites table)
ALTER TABLE orders ALTER COLUMN notes SET NOT NULL;
-- SAFE: Add constraint NOT VALID, then validate separately
ALTER TABLE orders ADD CONSTRAINT orders_notes_nn CHECK (notes IS NOT NULL) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_notes_nn;

-- DANGEROUS: Changing column type (rewrites table)
ALTER TABLE orders ALTER COLUMN amount TYPE DECIMAL(14,2);
-- SAFE: Add new column, dual-write, migrate, drop old

-- DANGEROUS: Renaming column (breaks all queries referencing old name)
-- SAFE: Add new column, add VIEW with old name, migrate gradually

-- DANGEROUS: Dropping column
-- SAFE: Stop reading it first, then drop in separate deploy
```

### Expand-Contract Migration Pattern:
```
Version 1 (current):  [first_name, last_name]
Version 2 (expand):   [first_name, last_name, full_name]  -- Add new
Version 3 (migrate):  Write to both, read from full_name
Version 4 (contract): [full_name]  -- Remove old after all consumers updated
```

---

## Problem 194: Multi-Table Inheritance Patterns

**Difficulty:** Hard | **Frequency:** High

**Problem:** Vehicles can be Cars, Trucks, or Motorcycles with shared and specific attributes.

### Single Table Inheritance (STI):
```sql
CREATE TABLE vehicles (
    vehicle_id UUID PRIMARY KEY,
    type VARCHAR(20) NOT NULL,  -- 'car', 'truck', 'motorcycle'
    make VARCHAR(100),
    model VARCHAR(100),
    year INT,
    -- Car-specific (NULL for others)
    num_doors INT,
    trunk_size_liters INT,
    -- Truck-specific
    payload_capacity_kg INT,
    num_axles INT,
    -- Motorcycle-specific
    engine_cc INT,
    has_sidecar BOOLEAN
);
```
**Pros:** Simple queries, no JOINs. **Cons:** Many NULL columns, wasted space, no type-specific constraints.

### Class Table Inheritance (CTI):
```sql
CREATE TABLE vehicles (
    vehicle_id UUID PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100),
    year INT
);

CREATE TABLE cars (
    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(vehicle_id),
    num_doors INT NOT NULL,
    trunk_size_liters INT
);

CREATE TABLE trucks (
    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(vehicle_id),
    payload_capacity_kg INT NOT NULL,
    num_axles INT NOT NULL
);
```
**Pros:** Clean schema, proper constraints. **Cons:** JOINs needed for full data.

### Concrete Table Inheritance:
```sql
CREATE TABLE cars (
    vehicle_id UUID PRIMARY KEY,
    make VARCHAR(100), model VARCHAR(100), year INT,
    num_doors INT NOT NULL
);

CREATE TABLE trucks (
    vehicle_id UUID PRIMARY KEY,
    make VARCHAR(100), model VARCHAR(100), year INT,
    payload_capacity_kg INT NOT NULL
);
-- No shared parent table. Each type is independent.
```
**Pros:** No JOINs ever. **Cons:** Can't query "all vehicles" easily, code duplication.

---

## Problem 195: Designing Idempotent Operations

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Network timeouts mean the client doesn't know if the server processed their request. Retrying must be safe.

```sql
-- Idempotency Key Table
CREATE TABLE idempotency_keys (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    user_id UUID NOT NULL,
    request_path VARCHAR(500),
    request_body_hash VARCHAR(64),
    response_code INT,
    response_body JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    -- Auto-cleanup old entries
    INDEX idx_created (created_at)
);

-- Processing flow:
BEGIN;

-- 1. Check if already processed
SELECT response_code, response_body FROM idempotency_keys
WHERE idempotency_key = @key
FOR UPDATE;  -- Lock to prevent concurrent duplicate processing

IF FOUND THEN
    -- Already processed → return cached response
    RETURN cached_response;
END IF;

-- 2. Insert key to claim it
INSERT INTO idempotency_keys (idempotency_key, user_id, request_path)
VALUES (@key, @user_id, @path);

-- 3. Process the actual request
-- ... business logic ...

-- 4. Store the response
UPDATE idempotency_keys 
SET response_code = 200, response_body = @response
WHERE idempotency_key = @key;

COMMIT;
```

**Natural Idempotency (design operations to be inherently safe):**
```sql
-- Idempotent by nature:
INSERT INTO ... ON CONFLICT DO NOTHING;  -- Safe to retry
UPDATE accounts SET balance = 500 WHERE id = 1;  -- Absolute value (not increment)

-- NOT idempotent (dangerous to retry):
UPDATE accounts SET balance = balance + 100;  -- Adds 100 each time!
INSERT INTO orders (...) VALUES (...);  -- Creates duplicates!
```

---

## Problem 196: Graph Data in Relational Databases

**Difficulty:** Hard | **Frequency:** High

**Problem:** Model a social network, knowledge graph, or dependency graph in SQL.

### Adjacency List (simplest):
```sql
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,
    label VARCHAR(100),
    properties JSONB
);

CREATE TABLE edges (
    edge_id UUID PRIMARY KEY,
    from_node UUID NOT NULL REFERENCES nodes(node_id),
    to_node UUID NOT NULL REFERENCES nodes(node_id),
    relationship VARCHAR(100) NOT NULL,  -- 'follows', 'likes', 'depends_on'
    properties JSONB,
    weight DECIMAL(10,4),
    INDEX idx_from (from_node, relationship),
    INDEX idx_to (to_node, relationship)
);
```

### Closure Table (for transitive closure / ancestor queries):
```sql
-- Stores ALL ancestor-descendant pairs (not just direct)
CREATE TABLE node_closure (
    ancestor_id UUID NOT NULL REFERENCES nodes(node_id),
    descendant_id UUID NOT NULL REFERENCES nodes(node_id),
    depth INT NOT NULL,  -- 0 = self, 1 = direct child, etc.
    PRIMARY KEY (ancestor_id, descendant_id)
);

-- Find all descendants of node X:
SELECT descendant_id, depth FROM node_closure WHERE ancestor_id = @x AND depth > 0;

-- Find all ancestors of node Y:
SELECT ancestor_id, depth FROM node_closure WHERE descendant_id = @y AND depth > 0;

-- Is X an ancestor of Y?
SELECT EXISTS(SELECT 1 FROM node_closure WHERE ancestor_id = @x AND descendant_id = @y);
```

### When to use Graph Database instead:
- More than 3-4 hops in traversals
- Complex pattern matching (friend-of-friend who also likes X)
- Real-time recommendation engines
- Path-finding algorithms (shortest path, PageRank)

---

## Problem 197: Designing for Data Privacy (GDPR/CCPA)

**Difficulty:** Hard | **Frequency:** Very High (Legal requirement)

```sql
-- Classify data sensitivity
CREATE TABLE data_classifications (
    table_name VARCHAR(100),
    column_name VARCHAR(100),
    classification ENUM('public', 'internal', 'confidential', 'pii', 'sensitive_pii') NOT NULL,
    retention_days INT,  -- NULL = indefinite
    requires_encryption BOOLEAN DEFAULT FALSE,
    requires_consent BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (table_name, column_name)
);

-- Consent tracking
CREATE TABLE user_consents (
    user_id UUID NOT NULL,
    consent_type VARCHAR(100) NOT NULL,  -- 'marketing', 'analytics', 'third_party_sharing'
    granted BOOLEAN NOT NULL,
    granted_at TIMESTAMP,
    revoked_at TIMESTAMP,
    ip_address INET,
    consent_version VARCHAR(20),  -- Version of privacy policy
    PRIMARY KEY (user_id, consent_type)
);

-- Data subject access request (DSAR) tracking
CREATE TABLE data_requests (
    request_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    request_type ENUM('access', 'rectification', 'erasure', 'portability', 'restriction') NOT NULL,
    status ENUM('received', 'processing', 'completed', 'denied') DEFAULT 'received',
    due_date DATE NOT NULL,  -- GDPR: 30 days
    completed_at TIMESTAMP,
    response_file_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Right to Erasure Implementation:**
```sql
-- Pseudonymization function (anonymize, don't delete for referential integrity)
CREATE OR REPLACE FUNCTION anonymize_user(p_user_id UUID) RETURNS VOID AS $$
BEGIN
    -- Anonymize user profile
    UPDATE users SET
        email = CONCAT('anon_', p_user_id, '@deleted.local'),
        name = 'Anonymous User',
        phone = NULL,
        address = NULL,
        date_of_birth = NULL,
        anonymized_at = NOW()
    WHERE user_id = p_user_id;
    
    -- Remove from analytics
    DELETE FROM user_interactions WHERE user_id = p_user_id;
    
    -- Keep orders (legal obligation) but anonymize
    UPDATE orders SET
        guest_name = 'Anonymous',
        shipping_address = NULL
    WHERE user_id = p_user_id;
    
    -- Audit the erasure
    INSERT INTO audit_log (action, record_id, details)
    VALUES ('GDPR_ERASURE', p_user_id::text, '{"reason": "user_request"}');
END;
$$ LANGUAGE plpgsql;
```

---

## Problem 198: Designing Time-Series Data Models

**Difficulty:** Hard | **Frequency:** High (IoT, Monitoring, Finance)

```sql
-- Hypertable approach (TimescaleDB)
CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    tags JSONB
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('metrics', 'time');

-- Continuous aggregates (auto-maintained materialized views)
CREATE MATERIALIZED VIEW metrics_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       device_id,
       metric_name,
       AVG(value) AS avg_value,
       MIN(value) AS min_value,
       MAX(value) AS max_value,
       COUNT(*) AS sample_count
FROM metrics
GROUP BY bucket, device_id, metric_name;

-- Retention policy (auto-delete old data)
SELECT add_retention_policy('metrics', INTERVAL '90 days');

-- Compression policy (old chunks compressed 10x)
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, metric_name'
);
SELECT add_compression_policy('metrics', INTERVAL '7 days');
```

**Downsampling Strategy:**
```
Raw data: 1-second resolution → retain 7 days
1-minute aggregates → retain 30 days
1-hour aggregates → retain 1 year
1-day aggregates → retain indefinitely
```

---

## Problem 199: Anti-Patterns in Database Design

**Difficulty:** Hard | **Frequency:** Very High (What NOT to do)

### Anti-Pattern 1: God Table
```sql
-- BAD: Everything in one massive table
CREATE TABLE everything (
    id BIGINT, type VARCHAR(50),
    name VARCHAR(500), description TEXT,
    user_id INT, order_id INT, product_id INT,
    amount DECIMAL, quantity INT,
    start_date DATE, end_date DATE,
    status VARCHAR(50), category VARCHAR(100),
    json_data TEXT, extra1 TEXT, extra2 TEXT, extra3 TEXT
    -- 200+ columns, 500M rows
);
-- FIX: Decompose into proper domain entities
```

### Anti-Pattern 2: Metadata Tribbles (Over-using EAV)
```sql
-- BAD: Everything is key-value
CREATE TABLE app_data (
    entity_id INT, key VARCHAR(100), value TEXT
);
-- Can't enforce types, constraints, or use indexes effectively
-- FIX: Use proper tables with typed columns
```

### Anti-Pattern 3: Jaywalking (Comma-Separated Lists)
```sql
-- BAD: Multiple values in one column
CREATE TABLE articles (
    article_id INT, 
    tags VARCHAR(1000)  -- "sql,database,design,interview"
);
-- Can't index, can't JOIN, can't enforce FK
-- FIX: Junction/bridge table
```

### Anti-Pattern 4: Implicit Columns (SELECT *)
```sql
-- BAD: Application depends on column order
INSERT INTO users VALUES (1, 'John', 'john@test.com');
-- Adding a column breaks this!
-- FIX: Always name columns explicitly
INSERT INTO users (id, name, email) VALUES (1, 'John', 'john@test.com');
```

### Anti-Pattern 5: Fear of JOINs (Premature Denormalization)
```sql
-- BAD: Duplicating data everywhere "to avoid JOINs"
CREATE TABLE orders (
    order_id INT,
    user_id INT,
    user_name VARCHAR(255),     -- Duplicated from users table
    user_email VARCHAR(255),    -- Duplicated
    user_address TEXT,          -- Duplicated
    product_name VARCHAR(255),  -- Duplicated from products
    product_price DECIMAL       -- Stale if product price changes!
);
-- FIX: Normalize first, denormalize only with data to prove it's needed
```

### Anti-Pattern 6: Phantom Files (Storing file paths without the file)
```sql
-- BAD: Storing file system paths with no guarantee file exists
CREATE TABLE documents (
    id INT,
    file_path VARCHAR(500)  -- "/mnt/nfs/uploads/doc123.pdf" — file may be deleted!
);
-- FIX: Use object storage (S3) with presigned URLs, or BLOB column for small files
```

---

## Problem 200: Database Design Interview Framework

**Difficulty:** Reference | **Frequency:** Every Interview

### Step-by-Step Approach for Any Schema Design Question:

```
1. CLARIFY REQUIREMENTS (5 minutes)
   - What are the core entities?
   - What are the relationships (1:1, 1:N, M:N)?
   - What are the access patterns (read vs write heavy)?
   - What's the scale (rows, QPS, data size)?
   - What consistency guarantees are needed?
   - Any compliance requirements (GDPR, SOX)?

2. IDENTIFY ENTITIES & RELATIONSHIPS (5 minutes)
   - Draw ER diagram (even on whiteboard)
   - Identify primary keys (natural vs surrogate)
   - Identify foreign key relationships
   - Note cardinality (one-to-many vs many-to-many)

3. DESIGN SCHEMA (10 minutes)
   - Start with 3NF (normalize)
   - Add appropriate data types
   - Add NOT NULL where required
   - Add CHECK constraints for business rules
   - Design composite keys for junction tables

4. DESIGN INDEXES (5 minutes)
   - Index for every WHERE clause in common queries
   - Composite indexes following equality-range-sort rule
   - Covering indexes for hot queries
   - Partial indexes for selective filters

5. ADDRESS SCALABILITY (5 minutes)
   - Partitioning strategy (if > 100M rows)
   - Read replicas (if read-heavy)
   - Sharding key (if distributed)
   - Caching strategy (Redis for hot data)

6. HANDLE EDGE CASES (5 minutes)
   - Concurrency (double-booking, lost updates)
   - Data integrity (what if service crashes mid-operation?)
   - Soft deletes vs hard deletes
   - Audit trail / compliance
   - Schema evolution (how to add features without downtime)
```

### Questions to Ask Interviewer:
- "What's the expected QPS for reads vs writes?"
- "Do we need real-time consistency or is eventual acceptable?"
- "What's the expected data retention period?"
- "Are there any regulatory requirements?"
- "What's the current team's tech stack preference?"
- "Is this greenfield or do we need to integrate with existing systems?"

---

## Master Reference: When to Use What

| Problem Type | Solution | Example |
|-------------|----------|---------|
| 2nd highest salary | DENSE_RANK window function | Problem 1 |
| Prevent double booking | Exclusion constraint (PG) | Problem 91 |
| Consecutive detection | Gaps & Islands technique | Problem 8, 13 |
| Hierarchical data | Recursive CTE + closure table | Problem 29 |
| Financial transactions | Double-entry ledger | Problem 111 |
| High concurrency writes | Optimistic locking + retry | Problem 131 |
| Distributed transactions | Saga + Outbox pattern | Problem 138, 141 |
| Slow queries | EXPLAIN + proper indexes | Problem 156 |
| Scale beyond 1 server | Sharding + consistent hash | Problem 171, 176 |
| Multi-region | CockroachDB or read replicas | Problem 175 |
| Time-series | TimescaleDB + partitioning | Problem 198 |
| Audit compliance | Trigger-based + temporal tables | Problem 192 |
| GDPR compliance | Anonymization + consent tracking | Problem 197 |
