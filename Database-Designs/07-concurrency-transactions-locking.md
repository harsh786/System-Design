# Concurrency, Transactions & Locking Problems (Problems 131-150)

## Staff Architect Level - Race Conditions, Isolation Levels, Deadlocks

---

## Problem 131: Lost Update Problem

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Two users simultaneously read a bank balance of $1000, each withdraws $100, and both write back $900 instead of the correct $800.

**Scenario:**
```
Time    Transaction 1          Transaction 2
T1      READ balance = 1000    
T2                             READ balance = 1000
T3      balance = 1000 - 100   
T4                             balance = 1000 - 100
T5      WRITE balance = 900    
T6                             WRITE balance = 900
Result: balance = 900 (should be 800!) — $100 lost!
```

**Solution 1: Atomic UPDATE (Best for simple operations)**
```sql
-- Never READ then WRITE separately. Use atomic operation:
UPDATE accounts 
SET balance = balance - 100 
WHERE account_id = @account_id AND balance >= 100;
-- The database handles concurrency internally
```

**Solution 2: Optimistic Locking (Version-based)**
```sql
-- Read with version
SELECT balance, version FROM accounts WHERE account_id = @id;
-- balance = 1000, version = 5

-- Update only if version unchanged
UPDATE accounts 
SET balance = @new_balance, version = version + 1
WHERE account_id = @id AND version = 5;
-- If affected_rows = 0 → someone else modified → RETRY
```

**Solution 3: Pessimistic Locking (SELECT FOR UPDATE)**
```sql
BEGIN;
SELECT balance FROM accounts WHERE account_id = @id FOR UPDATE;
-- Row is now locked until COMMIT/ROLLBACK
UPDATE accounts SET balance = balance - 100 WHERE account_id = @id;
COMMIT;
```

**Solution 4: Serializable Isolation**
```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
BEGIN;
SELECT balance FROM accounts WHERE account_id = @id;
-- ... application logic ...
UPDATE accounts SET balance = @new_balance WHERE account_id = @id;
COMMIT;
-- If conflict detected → automatic ROLLBACK with serialization failure error → RETRY
```

**When to use which:**
| Approach | Best For | Trade-off |
|----------|----------|-----------|
| Atomic UPDATE | Simple increment/decrement | Can't do complex logic between read and write |
| Optimistic Lock | Low contention, read-heavy | Application must handle retry |
| Pessimistic Lock | High contention, critical data | Reduces throughput, deadlock risk |
| Serializable | Complex multi-statement logic | Highest safety, lowest throughput |

---

## Problem 132: Phantom Reads

**Difficulty:** Hard | **Frequency:** High

**Problem:** A transaction reads a set of rows matching a condition, another transaction inserts a new row matching that condition, and the first transaction reads again seeing a "phantom" row.

```
Time    Transaction 1                              Transaction 2
T1      SELECT COUNT(*) FROM orders 
        WHERE status='pending'  → 10
T2                                                 INSERT INTO orders (..., 'pending')
T3                                                 COMMIT
T4      SELECT COUNT(*) FROM orders 
        WHERE status='pending'  → 11  (PHANTOM!)
```

**Why it matters:** If T1 is computing something based on the count (like "process all pending orders"), it might miss one.

**Solution 1: SERIALIZABLE isolation (prevents phantoms)**
```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
BEGIN;
-- PostgreSQL uses SSI (Serializable Snapshot Isolation)
-- All reads are snapshot-consistent, phantoms detected at commit
SELECT * FROM orders WHERE status = 'pending';
-- Process orders...
COMMIT;
```

**Solution 2: Range Locking (InnoDB with REPEATABLE READ + gap locks)**
```sql
-- In InnoDB, SELECT ... FOR UPDATE locks the INDEX RANGE
-- This prevents inserts into that range
SELECT * FROM orders WHERE status = 'pending' FOR UPDATE;
-- Gap lock prevents new 'pending' inserts until COMMIT
```

**Solution 3: Application-level resolution**
```sql
-- Use advisory locks for business process coordination
SELECT pg_advisory_lock(hashtext('process_pending_orders'));
-- Only one process can hold this lock
-- ... process all pending orders ...
SELECT pg_advisory_unlock(hashtext('process_pending_orders'));
```

---

## Problem 133: Deadlock Detection and Prevention

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Two transactions each hold a lock that the other needs, creating a circular dependency.

```
Time    Transaction 1                   Transaction 2
T1      LOCK account A                  
T2                                      LOCK account B
T3      TRY LOCK account B → WAIT      
T4                                      TRY LOCK account A → WAIT
DEADLOCK! Both waiting forever.
```

**Prevention Strategy 1: Ordered Locking (The Golden Rule)**
```sql
-- ALWAYS lock resources in a consistent, deterministic order
-- E.g., always lock the account with the LOWER ID first

-- Transfer from account 7 to account 3:
-- Lock order: 3 (lower), then 7 (higher)
BEGIN;
SELECT * FROM accounts WHERE account_id = 3 FOR UPDATE;
SELECT * FROM accounts WHERE account_id = 7 FOR UPDATE;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 7;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 3;
COMMIT;
```

**Prevention Strategy 2: Lock Timeout**
```sql
-- MySQL
SET innodb_lock_wait_timeout = 5;  -- 5 seconds max wait

-- PostgreSQL
SET lock_timeout = '5s';
BEGIN;
SELECT * FROM accounts WHERE id = @id FOR UPDATE;
-- If can't acquire within 5s → ERROR, not deadlock
```

**Prevention Strategy 3: NOWAIT**
```sql
BEGIN;
SELECT * FROM accounts WHERE id = @id FOR UPDATE NOWAIT;
-- If row already locked → immediate ERROR (no waiting)
-- Application catches error and retries
```

**Prevention Strategy 4: SKIP LOCKED (for work queues)**
```sql
-- Process next available task, skip locked ones
SELECT task_id, payload FROM task_queue
WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
-- Multiple workers can safely dequeue without conflicts
```

---

## Problem 134: Write Skew Anomaly

**Difficulty:** Expert | **Frequency:** High (Hospital on-call, Inventory systems)

**Problem:** Two transactions read the same data, make decisions based on it, and write to DIFFERENT rows — but the combination of their writes violates a constraint.

**Classic Example: Hospital On-Call**
```
Business rule: At least 1 doctor must be on call at all times.
Currently: Doctor A (on call), Doctor B (on call)

Time    Transaction 1 (Dr. A)          Transaction 2 (Dr. B)
T1      SELECT COUNT(*) FROM doctors 
        WHERE on_call=TRUE  → 2          
T2      "2 on call, safe to leave"       SELECT COUNT(*) FROM doctors 
                                         WHERE on_call=TRUE  → 2
T3      UPDATE doctors SET on_call=FALSE  "2 on call, safe to leave"
        WHERE id = 'A'                   
T4                                       UPDATE doctors SET on_call=FALSE
                                         WHERE id = 'B'
T5      COMMIT                           COMMIT

Result: 0 doctors on call! VIOLATION!
```

**Why REPEATABLE READ doesn't help:** Each transaction modifies a DIFFERENT row, so row-level locks don't conflict.

**Solution 1: SERIALIZABLE (PostgreSQL SSI detects this)**
```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
BEGIN;
SELECT COUNT(*) FROM doctors WHERE on_call = TRUE;
-- If count > 1, proceed
UPDATE doctors SET on_call = FALSE WHERE id = @my_id;
COMMIT;
-- One transaction will get serialization_failure error → retry
```

**Solution 2: Materializing the constraint**
```sql
-- Create a "lock row" that both must acquire
CREATE TABLE on_call_lock (
    id INT PRIMARY KEY DEFAULT 1,
    CHECK (id = 1)  -- Only one row ever
);
INSERT INTO on_call_lock VALUES (1);

BEGIN;
SELECT * FROM on_call_lock FOR UPDATE;  -- Both transactions now conflict
SELECT COUNT(*) FROM doctors WHERE on_call = TRUE;
UPDATE doctors SET on_call = FALSE WHERE id = @my_id;
COMMIT;
```

**Solution 3: Application-level CHECK constraint**
```sql
-- Use a trigger
CREATE TRIGGER check_on_call_minimum
AFTER UPDATE ON doctors
FOR EACH ROW
BEGIN
    IF (SELECT COUNT(*) FROM doctors WHERE on_call = TRUE) < 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'At least 1 doctor must be on call';
    END IF;
END;
```

---

## Problem 135: Transaction Isolation Levels Deep Dive

**Difficulty:** Expert | **Frequency:** Very High (Interview fundamental)

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read | Write Skew | Performance |
|-----------------|------------|---------------------|--------------|------------|-------------|
| READ UNCOMMITTED | Possible | Possible | Possible | Possible | Fastest |
| READ COMMITTED | Prevented | Possible | Possible | Possible | Fast |
| REPEATABLE READ | Prevented | Prevented | Possible* | Possible | Medium |
| SERIALIZABLE | Prevented | Prevented | Prevented | Prevented | Slowest |

*MySQL InnoDB REPEATABLE READ prevents phantoms with gap locks (non-standard behavior)

**PostgreSQL vs MySQL:**
```
PostgreSQL:
- Uses MVCC (Multi-Version Concurrency Control)
- Default: READ COMMITTED
- SERIALIZABLE uses SSI (Serializable Snapshot Isolation) — no locks needed!
- Readers never block writers, writers never block readers

MySQL InnoDB:
- Uses MVCC + Locking
- Default: REPEATABLE READ (with gap locks preventing phantoms)
- SELECT FOR UPDATE uses next-key locking (record + gap)
- More prone to deadlocks than PostgreSQL
```

---

## Problem 136: Implementing a Job Queue with Database

**Difficulty:** Hard | **Frequency:** Very High

**Problem:** Multiple worker processes need to dequeue tasks safely without processing the same task twice.

```sql
CREATE TABLE job_queue (
    job_id UUID PRIMARY KEY,
    queue_name VARCHAR(100) NOT NULL DEFAULT 'default',
    payload JSONB NOT NULL,
    priority INT DEFAULT 0,
    status ENUM('pending', 'processing', 'completed', 'failed', 'dead') DEFAULT 'pending',
    max_retries INT DEFAULT 3,
    retry_count INT DEFAULT 0,
    locked_by VARCHAR(100),  -- Worker ID
    locked_at TIMESTAMP,
    scheduled_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_dequeue (queue_name, status, priority DESC, scheduled_at),
    INDEX idx_lock_timeout (status, locked_at)
);
```

**Safe Dequeue Pattern (SKIP LOCKED):**
```sql
-- Worker dequeues next available job
BEGIN;

UPDATE job_queue
SET status = 'processing', 
    locked_by = @worker_id, 
    locked_at = NOW(),
    started_at = NOW()
WHERE job_id = (
    SELECT job_id FROM job_queue
    WHERE queue_name = @queue_name
      AND status = 'pending'
      AND scheduled_at <= NOW()
    ORDER BY priority DESC, scheduled_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED  -- Skip jobs being processed by others
)
RETURNING *;

COMMIT;
```

**Stale Lock Recovery (heartbeat timeout):**
```sql
-- Cron job: Reset jobs that have been locked too long (worker crashed)
UPDATE job_queue
SET status = 'pending', locked_by = NULL, locked_at = NULL,
    retry_count = retry_count + 1
WHERE status = 'processing'
  AND locked_at < NOW() - INTERVAL '5 minutes';

-- Move to dead-letter after max retries
UPDATE job_queue
SET status = 'dead'
WHERE status = 'pending' AND retry_count >= max_retries;
```

---

## Problem 137: Implementing Distributed Locks with Database

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE distributed_locks (
    lock_name VARCHAR(255) PRIMARY KEY,
    locked_by VARCHAR(100) NOT NULL,  -- Instance ID
    locked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    metadata JSONB
);

-- Acquire lock (atomic)
INSERT INTO distributed_locks (lock_name, locked_by, expires_at)
VALUES (@lock_name, @instance_id, NOW() + INTERVAL '30 seconds')
ON CONFLICT (lock_name) DO UPDATE
SET locked_by = EXCLUDED.locked_by,
    locked_at = NOW(),
    expires_at = EXCLUDED.expires_at
WHERE distributed_locks.expires_at < NOW();  -- Only if existing lock expired

-- Check if we got it
-- If affected_rows = 1 → acquired
-- If affected_rows = 0 → someone else holds it

-- Release lock
DELETE FROM distributed_locks
WHERE lock_name = @lock_name AND locked_by = @instance_id;

-- Extend lock (heartbeat)
UPDATE distributed_locks
SET expires_at = NOW() + INTERVAL '30 seconds'
WHERE lock_name = @lock_name AND locked_by = @instance_id;
```

**PostgreSQL Advisory Locks (better performance):**
```sql
-- Session-level lock (released on disconnect)
SELECT pg_advisory_lock(hashtext('my_resource'));
-- ... critical section ...
SELECT pg_advisory_unlock(hashtext('my_resource'));

-- Try without blocking:
SELECT pg_try_advisory_lock(hashtext('my_resource'));
-- Returns TRUE if acquired, FALSE if held by someone else
```

---

## Problem 138: Saga Pattern for Distributed Transactions

**Difficulty:** Expert | **Frequency:** Very High (Microservices)

**Problem:** Order placement involves: Reserve Inventory → Charge Payment → Send Confirmation. If payment fails, must undo inventory reservation.

```sql
CREATE TABLE sagas (
    saga_id UUID PRIMARY KEY,
    saga_type VARCHAR(100) NOT NULL,  -- 'place_order', 'transfer_funds'
    status ENUM('started', 'compensating', 'completed', 'failed') DEFAULT 'started',
    payload JSONB NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    INDEX idx_status (status)
);

CREATE TABLE saga_steps (
    step_id UUID PRIMARY KEY,
    saga_id UUID NOT NULL REFERENCES sagas(saga_id),
    step_order INT NOT NULL,
    step_name VARCHAR(100) NOT NULL,  -- 'reserve_inventory', 'charge_payment'
    status ENUM('pending', 'executing', 'completed', 'compensating', 'compensated', 'failed') DEFAULT 'pending',
    request_payload JSONB,
    response_payload JSONB,
    compensation_payload JSONB,  -- Data needed to undo this step
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    UNIQUE KEY uk_saga_order (saga_id, step_order)
);
```

**Saga Execution Logic:**
```sql
-- Orchestrator pattern: Central coordinator drives steps

-- Step 1: Reserve inventory
UPDATE saga_steps SET status = 'executing', started_at = NOW()
WHERE saga_id = @saga_id AND step_order = 1;
-- Call inventory service...
-- On success:
UPDATE saga_steps SET status = 'completed', response_payload = @response, completed_at = NOW()
WHERE saga_id = @saga_id AND step_order = 1;

-- Step 2: Charge payment
-- ... similar ...
-- On FAILURE:
UPDATE saga_steps SET status = 'failed', error_message = @error
WHERE saga_id = @saga_id AND step_order = 2;

-- Trigger compensation for all completed steps (reverse order)
UPDATE sagas SET status = 'compensating' WHERE saga_id = @saga_id;

-- Compensate Step 1: Release inventory
UPDATE saga_steps SET status = 'compensating' 
WHERE saga_id = @saga_id AND step_order = 1 AND status = 'completed';
-- Call inventory service to release...
UPDATE saga_steps SET status = 'compensated' WHERE saga_id = @saga_id AND step_order = 1;
```

---

## Problem 139: Read-Your-Writes Consistency

**Difficulty:** Hard | **Frequency:** High (Distributed systems)

**Problem:** User updates their profile, page refreshes, but reads from a replica that hasn't caught up yet — shows old data.

**Solutions:**

**1. Sticky Sessions (route user to same replica)**
```sql
-- Tag the user's session with a LSN (Log Sequence Number)
-- After write: Record the write LSN
-- Before read: Ensure replica has caught up to that LSN

-- PostgreSQL: Check replica lag
SELECT pg_last_wal_replay_lsn() >= @user_write_lsn;
-- If FALSE, route to primary
```

**2. Causal Consistency Token**
```sql
-- Application layer:
-- After write → return consistency_token (timestamp or LSN)
-- Client includes token in subsequent reads
-- Backend: if token > replica_position, read from primary

-- Implementation in middleware:
CREATE TABLE consistency_tokens (
    user_id UUID PRIMARY KEY,
    last_write_lsn PG_LSN NOT NULL,
    last_write_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL  -- Fall back to replica after X seconds
);
```

**3. Synchronous replication for critical reads**
```sql
-- PostgreSQL: Per-transaction synchronous commit
SET synchronous_commit = 'remote_apply';
-- Ensures write is applied on replica before returning to client
-- Slower but guarantees read-your-writes from any replica
```

---

## Problem 140: Implementing Rate Limiting with Database

**Difficulty:** Medium | **Frequency:** Very High

```sql
CREATE TABLE rate_limits (
    key VARCHAR(255) NOT NULL,  -- "user:123:api", "ip:1.2.3.4:login"
    window_start TIMESTAMP NOT NULL,
    request_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);
```

**Fixed Window:**
```sql
-- Increment counter for current window
INSERT INTO rate_limits (key, window_start, request_count)
VALUES (@key, date_trunc('minute', NOW()), 1)
ON CONFLICT (key, window_start)
DO UPDATE SET request_count = rate_limits.request_count + 1;

-- Check if over limit
SELECT request_count FROM rate_limits
WHERE key = @key AND window_start = date_trunc('minute', NOW());
-- If >= limit → reject
```

**Sliding Window Log:**
```sql
CREATE TABLE request_log (
    key VARCHAR(255) NOT NULL,
    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_key_time (key, requested_at)
);

-- Check rate
SELECT COUNT(*) FROM request_log
WHERE key = @key AND requested_at > NOW() - INTERVAL '1 minute';
-- If >= limit → reject, else INSERT

-- Cleanup old entries periodically
DELETE FROM request_log WHERE requested_at < NOW() - INTERVAL '1 hour';
```

**Token Bucket (with database):**
```sql
CREATE TABLE token_buckets (
    key VARCHAR(255) PRIMARY KEY,
    tokens DECIMAL(10,2) NOT NULL,
    max_tokens INT NOT NULL,
    refill_rate DECIMAL(10,4) NOT NULL,  -- tokens per second
    last_refill TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Consume a token (atomic)
UPDATE token_buckets
SET tokens = LEAST(
        max_tokens,
        tokens + refill_rate * EXTRACT(EPOCH FROM (NOW() - last_refill))
    ) - 1,
    last_refill = NOW()
WHERE key = @key
  AND LEAST(
        max_tokens,
        tokens + refill_rate * EXTRACT(EPOCH FROM (NOW() - last_refill))
    ) >= 1;
-- If affected_rows = 0 → rate limited
```

**Architect Note:** In production, rate limiting belongs in Redis (INCR + EXPIRE), not SQL. SQL-based is acceptable for:
- Low-traffic APIs
- Audit requirements
- When Redis isn't available

---

## Problem 141: Implementing Outbox Pattern (Transactional Messaging)

**Difficulty:** Hard | **Frequency:** Very High (Event-driven architectures)

**Problem:** You need to update a database AND publish an event atomically. Can't use distributed transaction between DB and message broker.

```sql
-- The Outbox: Events stored in same DB as business data
CREATE TABLE outbox_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(100) NOT NULL,  -- 'Order', 'Payment'
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,  -- 'OrderCreated', 'PaymentSucceeded'
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP,  -- NULL = not yet published
    INDEX idx_unpublished (published_at, created_at)
);

-- Business operation + event in SAME transaction
BEGIN;

INSERT INTO orders (order_id, user_id, total_amount, status)
VALUES (@order_id, @user_id, @total, 'confirmed');

INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload)
VALUES ('Order', @order_id, 'OrderCreated', 
        jsonb_build_object('order_id', @order_id, 'user_id', @user_id, 'total', @total));

COMMIT;  -- Both succeed or both fail — atomic!
```

**Outbox Poller (publishes to Kafka/RabbitMQ):**
```sql
-- Poller grabs unpublished events
SELECT event_id, aggregate_type, event_type, payload
FROM outbox_events
WHERE published_at IS NULL
ORDER BY created_at
LIMIT 100
FOR UPDATE SKIP LOCKED;

-- After successfully publishing to message broker:
UPDATE outbox_events SET published_at = NOW()
WHERE event_id IN (@published_ids);
```

**Alternative: CDC (Change Data Capture)**
- Debezium reads the database WAL/binlog directly
- Publishes changes to Kafka automatically
- No polling needed, lower latency
- More operationally complex

---

## Problem 142: Multi-Version Concurrency Control (MVCC) Internals

**Difficulty:** Expert | **Frequency:** High (Deep architecture interviews)

**How PostgreSQL MVCC works:**

```
Every row has hidden system columns:
- xmin: Transaction ID that INSERT'd this row
- xmax: Transaction ID that DELETE'd/UPDATE'd this row (0 if alive)
- ctid: Physical location (page, offset)

When you UPDATE a row:
1. Old row: xmax set to current transaction ID
2. New row: Inserted with xmin = current transaction ID
3. Both versions exist simultaneously!

Visibility rules (for transaction T reading):
- Row is visible if:
  - xmin is committed AND xmin < T's snapshot
  - xmax is 0 OR xmax is not committed OR xmax > T's snapshot
```

**Implications:**
```sql
-- VACUUM is necessary because:
-- 1. Dead tuples (old versions) accumulate
-- 2. They waste disk space
-- 3. Slow down sequential scans
-- 4. Transaction ID wraparound (every ~2B transactions)

-- Check bloat:
SELECT relname, n_dead_tup, n_live_tup, 
       ROUND(n_dead_tup * 100.0 / NULLIF(n_live_tup, 0), 2) AS dead_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

---

## Problem 143: Handling Long-Running Transactions

**Difficulty:** Hard | **Frequency:** High

**Problem:** A long-running report query holds a snapshot, preventing VACUUM from cleaning dead tuples, leading to table bloat.

**Solutions:**

```sql
-- 1. Set statement timeout for long queries
SET statement_timeout = '300s';  -- Kill after 5 minutes

-- 2. Use idle_in_transaction_session_timeout
SET idle_in_transaction_session_timeout = '60s';

-- 3. Monitor long transactions
SELECT pid, state, query_start, NOW() - query_start AS duration,
       LEFT(query, 100) AS query_preview
FROM pg_stat_activity
WHERE state != 'idle'
  AND NOW() - query_start > INTERVAL '5 minutes'
ORDER BY duration DESC;

-- 4. Use READ COMMITTED for reports (doesn't hold snapshot across statements)
-- 5. Use a read replica for reports
-- 6. Use pg_terminate_backend() for stuck transactions
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE NOW() - xact_start > INTERVAL '1 hour' AND state = 'idle in transaction';
```

---

## Problem 144: Implementing Exactly-Once Processing

**Difficulty:** Expert | **Frequency:** Very High

**Problem:** Events may be delivered multiple times (at-least-once). Ensure each is processed exactly once.

```sql
-- Idempotency table
CREATE TABLE processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT NOW(),
    result JSONB
);

-- Process event exactly once:
BEGIN;

-- Try to claim this event
INSERT INTO processed_events (event_id) VALUES (@event_id)
ON CONFLICT (event_id) DO NOTHING;

-- Check if we got it
IF FOUND THEN
    -- First time processing → do the work
    -- ... business logic ...
    UPDATE processed_events SET result = @result WHERE event_id = @event_id;
ELSE
    -- Already processed → skip (or return cached result)
    SELECT result FROM processed_events WHERE event_id = @event_id;
END IF;

COMMIT;
```

**With deduplication window (don't store forever):**
```sql
CREATE TABLE processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (processed_at);

-- Create daily partitions, drop after 7 days
-- This prevents the table from growing indefinitely
```

---

## Problem 145: Database Connection Pooling Strategies

**Difficulty:** Hard | **Frequency:** High

**Problem:** Application has 100 instances, each wanting 20 connections = 2000 connections. PostgreSQL struggles above ~500.

**Solutions:**

```
1. PgBouncer (Transaction-level pooling):
   - 2000 app connections → 100 actual PG connections
   - Connection returned to pool after each transaction
   - Cannot use: prepared statements, SET commands, advisory locks

2. Connection Pool Sizing Formula (from HikariCP docs):
   connections = (core_count * 2) + effective_spindle_count
   For SSD: connections ≈ core_count * 2 + 1
   
3. Application-level pooling:
   - HikariCP (Java) - fastest
   - pgxpool (Go)
   - asyncpg with pool (Python)
   
   Configuration:
   - min_pool_size: 5
   - max_pool_size: 20
   - connection_timeout: 30s
   - idle_timeout: 600s
   - max_lifetime: 1800s (prevent stale connections)
```

**Monitor connection usage:**
```sql
SELECT state, COUNT(*), 
       array_agg(DISTINCT application_name) AS apps
FROM pg_stat_activity
GROUP BY state;

-- Check for connection leaks
SELECT pid, state, query_start, application_name
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND NOW() - state_change > INTERVAL '5 minutes';
```

---

## Problem 146: Implementing Optimistic Concurrency with ETags

**Difficulty:** Medium | **Frequency:** High (REST APIs)

```sql
-- Add version/etag to entities
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY,
    title VARCHAR(500),
    content TEXT,
    version INT NOT NULL DEFAULT 1,
    etag VARCHAR(64) GENERATED ALWAYS AS (MD5(version::text || updated_at::text)) STORED,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- API: GET /documents/123
-- Response Header: ETag: "abc123def456"

-- API: PUT /documents/123
-- Request Header: If-Match: "abc123def456"
UPDATE documents
SET title = @new_title, 
    content = @new_content,
    version = version + 1,
    updated_at = NOW()
WHERE doc_id = @doc_id AND etag = @provided_etag;

-- If affected_rows = 0 → 409 Conflict (someone else modified)
-- If affected_rows = 1 → 200 OK (return new ETag)
```

---

## Problem 147: Preventing Inventory Overselling Under High Concurrency

**Difficulty:** Expert | **Frequency:** Very High (E-commerce flash sales)

**Multi-layer defense:**

```sql
-- Layer 1: Redis fast-path (handle 100K+ req/sec)
-- DECR inventory_key → if >= 0, proceed; else reject early

-- Layer 2: Database with pessimistic lock
BEGIN;
SELECT quantity_available FROM inventory 
WHERE product_id = @pid AND warehouse_id = @wid
FOR UPDATE;

-- Application check
IF quantity_available >= @requested_qty THEN
    UPDATE inventory 
    SET quantity_available = quantity_available - @requested_qty,
        quantity_reserved = quantity_reserved + @requested_qty
    WHERE product_id = @pid AND warehouse_id = @wid;
    -- Success
ELSE
    -- Out of stock
    ROLLBACK;
END IF;
COMMIT;

-- Layer 3: CHECK constraint as final safety net
ALTER TABLE inventory ADD CONSTRAINT chk_no_negative 
    CHECK (quantity_available >= 0);
```

**PostgreSQL's SKIP LOCKED for batch allocation:**
```sql
-- Allocate inventory from multiple warehouses
WITH available_inventory AS (
    SELECT inventory_id, quantity_available
    FROM inventory
    WHERE product_id = @pid AND quantity_available > 0
    ORDER BY warehouse_priority
    FOR UPDATE SKIP LOCKED
    LIMIT 5
)
UPDATE inventory i
SET quantity_available = i.quantity_available - @qty
FROM available_inventory ai
WHERE i.inventory_id = ai.inventory_id
RETURNING i.warehouse_id, @qty AS allocated;
```

---

## Problem 148: Implementing Event Sourcing with Database

**Difficulty:** Expert | **Frequency:** High

```sql
-- Event Store
CREATE TABLE events (
    event_id BIGSERIAL PRIMARY KEY,
    stream_id UUID NOT NULL,  -- Aggregate ID (e.g., order_id)
    stream_type VARCHAR(100) NOT NULL,  -- 'Order', 'Account'
    event_type VARCHAR(100) NOT NULL,  -- 'OrderCreated', 'ItemAdded'
    event_data JSONB NOT NULL,
    metadata JSONB,  -- causation_id, correlation_id, user_id
    version INT NOT NULL,  -- Per-stream version for optimistic concurrency
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Optimistic concurrency: No two events with same stream+version
    UNIQUE KEY uk_stream_version (stream_id, version),
    INDEX idx_stream (stream_id, version),
    INDEX idx_type (event_type, created_at)
);

-- Append event (with optimistic concurrency)
INSERT INTO events (stream_id, stream_type, event_type, event_data, version)
VALUES (@stream_id, 'Order', 'ItemAdded', @data, @expected_version + 1);
-- If UNIQUE violation → concurrent modification → reload and retry

-- Rebuild aggregate state (replay events)
SELECT event_type, event_data, version
FROM events
WHERE stream_id = @order_id
ORDER BY version;
-- Apply each event to rebuild current state

-- Snapshots (for performance with long event streams)
CREATE TABLE snapshots (
    stream_id UUID PRIMARY KEY,
    stream_type VARCHAR(100) NOT NULL,
    version INT NOT NULL,
    state JSONB NOT NULL,  -- Serialized aggregate state
    created_at TIMESTAMP DEFAULT NOW()
);

-- Rebuild from snapshot + subsequent events
SELECT state FROM snapshots WHERE stream_id = @id;
SELECT * FROM events WHERE stream_id = @id AND version > @snapshot_version ORDER BY version;
```

---

## Problem 149: Handling Clock Skew in Distributed Systems

**Difficulty:** Expert | **Frequency:** High

**Problem:** Different servers have slightly different clocks. Using `NOW()` can cause ordering issues.

**Solutions:**

```sql
-- 1. Hybrid Logical Clocks (HLC)
-- Combine physical time with logical counter
CREATE TABLE events (
    id UUID PRIMARY KEY,
    hlc_timestamp BIGINT NOT NULL,  -- Physical time (ms) << 16 | logical_counter
    -- Guarantees: if event A caused event B, HLC(A) < HLC(B)
    INDEX idx_hlc (hlc_timestamp)
);

-- 2. Snowflake IDs (Twitter-style)
-- 41 bits: timestamp (ms) — good for 69 years
-- 10 bits: machine ID — 1024 machines
-- 12 bits: sequence — 4096 per ms per machine
-- Total: 63 bits, time-ordered, globally unique

-- 3. ULID (Universally Unique Lexicographically Sortable Identifier)
-- 48 bits: timestamp (ms)
-- 80 bits: randomness
-- Base32 encoded, sortable, 26 characters

-- 4. Lamport Timestamps (for causal ordering)
CREATE TABLE distributed_events (
    node_id INT NOT NULL,
    lamport_clock BIGINT NOT NULL,
    wall_clock TIMESTAMP NOT NULL,
    payload JSONB,
    PRIMARY KEY (node_id, lamport_clock)
);
```

---

## Problem 150: Transaction Design Patterns Summary

**Difficulty:** Reference | **Frequency:** Every Interview

### Pattern Cheat Sheet:

| Pattern | Use When | Implementation |
|---------|----------|----------------|
| Atomic UPDATE | Simple counter/balance changes | `UPDATE ... SET x = x + 1` |
| Optimistic Lock | Low contention reads | Version column + retry |
| Pessimistic Lock | High contention writes | `SELECT ... FOR UPDATE` |
| SKIP LOCKED | Work queues | `FOR UPDATE SKIP LOCKED` |
| Advisory Lock | Application-level mutex | `pg_advisory_lock()` |
| Exclusion Constraint | Preventing overlaps | `EXCLUDE USING gist (...)` |
| Outbox Pattern | DB + Message broker atomicity | Same-transaction event table |
| Saga Pattern | Cross-service transactions | Compensating transactions |
| Idempotency Key | Duplicate request handling | Unique key per operation |
| Event Sourcing | Audit + temporal queries | Append-only event log |

### Transaction Anti-Patterns:

1. **Holding locks during external calls** — Never do I/O inside a transaction
2. **Long-running transactions** — Keep transactions as short as possible
3. **Implicit transactions** — Always use explicit BEGIN/COMMIT
4. **Nested transactions** — Use SAVEPOINTs instead (savepoints, not true nested)
5. **Mixing DDL and DML** — DDL causes implicit commit in MySQL
6. **Not handling deadlocks** — Always have retry logic
7. **SELECT without FOR UPDATE before UPDATE** — Lost update problem
8. **Using READ UNCOMMITTED** — Almost never correct; only for approximate counts
