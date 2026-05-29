# Concurrency & Locking Deep Dive (Staff Engineer / Architect Level)

> This document covers database concurrency internals, locking mechanisms, and real-world concurrency patterns at a level expected in Staff Engineer / Architect interviews. Includes timeline diagrams, database-level mechanics, and production-grade solutions.

---

## 1. Database Concurrency Fundamentals

### MVCC (Multi-Version Concurrency Control)

MVCC allows multiple transactions to read data simultaneously without blocking each other. Each transaction sees a consistent snapshot of the database.

#### PostgreSQL MVCC Implementation

```
┌───────────────────────────────────────────────────────────────┐
│ PostgreSQL Tuple Versioning                                    │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Each row (tuple) has hidden columns:                          │
│    xmin: Transaction ID that INSERTED this tuple               │
│    xmax: Transaction ID that DELETED/UPDATED this tuple        │
│          (0 if still live)                                      │
│    ctid: Physical location (page, offset)                      │
│                                                                 │
│  UPDATE = INSERT new version + mark old version deleted        │
│                                                                 │
│  Version Chain:                                                 │
│  ┌────────────────┐     ┌────────────────┐                    │
│  │ Tuple v1       │     │ Tuple v2       │                    │
│  │ xmin=100       │────→│ xmin=105       │                    │
│  │ xmax=105       │     │ xmax=0 (live)  │                    │
│  │ name='John'    │     │ name='Jane'    │                    │
│  └────────────────┘     └────────────────┘                    │
│  (dead, will be                (current version)               │
│   vacuumed later)                                              │
│                                                                 │
└───────────────────────────────────────────────────────────────┘
```

**Visibility rule**: A tuple is visible to transaction T if:
- `xmin` is committed AND `xmin` < T's snapshot
- `xmax` is either 0 (not deleted) OR `xmax` > T's snapshot OR `xmax` is aborted

#### InnoDB (MySQL) MVCC Implementation

```
┌───────────────────────────────────────────────────────────────┐
│ InnoDB MVCC with Undo Log                                      │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  Clustered Index Record:                                       │
│  ┌─────────────────────────────────────────────┐              │
│  │ id=1 │ name='Jane' │ DB_TRX_ID=105 │ ROLL_PTR──────┐     │
│  └─────────────────────────────────────────────┘       │     │
│                                                          │     │
│  Undo Log (rollback segment):                           ▼     │
│  ┌─────────────────────────────────────────────┐              │
│  │ id=1 │ name='John' │ DB_TRX_ID=100 │ ROLL_PTR──────┐     │
│  └─────────────────────────────────────────────┘       │     │
│                                                          ▼     │
│  ┌─────────────────────────────────────────────┐              │
│  │ id=1 │ name='Jack' │ DB_TRX_ID=95  │ NULL   │             │
│  └─────────────────────────────────────────────┘              │
│                                                                 │
│  Transaction 102 reads: follows undo chain until               │
│  finding version with DB_TRX_ID <= 102's snapshot             │
│  → sees name='John' (TRX_ID=100, committed before 102)       │
│                                                                 │
└───────────────────────────────────────────────────────────────┘
```

### Lock-Based vs MVCC Comparison

| Aspect | Lock-Based (2PL) | MVCC |
|--------|-----------------|------|
| Readers block writers | Yes | No |
| Writers block readers | Yes | No |
| Writers block writers | Yes | Yes (on same row) |
| Phantom prevention | Gap locks | SSI (PostgreSQL) / Gap locks (InnoDB) |
| Read consistency | Lock-based | Snapshot-based |
| Deadlock possibility | High | Lower (but still possible for writes) |
| Storage overhead | Locks only | Undo logs / multiple tuple versions |

---

## 2. Concurrency Anomalies In-Depth

### Dirty Read

A transaction reads data written by another transaction that has not yet committed.

```
Timeline:
─────────────────────────────────────────────────────────────────
T1:  BEGIN
T1:  UPDATE accounts SET balance = 500 WHERE id = 1  (was 1000)
                                T2: BEGIN
                                T2: SELECT balance FROM accounts WHERE id = 1
                                T2: → reads 500 (DIRTY! T1 hasn't committed)
T1:  ROLLBACK  ← T1 aborts!
                                T2: Uses balance=500 for calculation
                                T2: COMMIT
                                    ← T2 made decision based on data that NEVER existed!
─────────────────────────────────────────────────────────────────

Prevention: READ_COMMITTED or higher (virtually all production systems)
JPA: @Transactional(isolation = Isolation.READ_COMMITTED)
```

### Non-Repeatable Read

A transaction reads the same row twice and gets different values because another transaction modified it in between.

```
Timeline:
─────────────────────────────────────────────────────────────────
T1:  BEGIN
T1:  SELECT balance FROM accounts WHERE id = 1 → 1000
                                T2: BEGIN
                                T2: UPDATE accounts SET balance = 500 WHERE id = 1
                                T2: COMMIT ✓
T1:  SELECT balance FROM accounts WHERE id = 1 → 500 (DIFFERENT!)
T1:  ← Business logic assumed balance is stable within transaction!
T1:  COMMIT
─────────────────────────────────────────────────────────────────

Prevention: REPEATABLE_READ or higher
JPA: @Transactional(isolation = Isolation.REPEATABLE_READ)
```

### Phantom Read

A transaction re-executes a query with a range condition and finds new rows that didn't exist before.

```
Timeline:
─────────────────────────────────────────────────────────────────
T1:  BEGIN
T1:  SELECT * FROM orders WHERE status = 'PENDING' → 3 rows
                                T2: BEGIN
                                T2: INSERT INTO orders (status) VALUES ('PENDING')
                                T2: COMMIT ✓
T1:  SELECT * FROM orders WHERE status = 'PENDING' → 4 rows (PHANTOM!)
T1:  ← Report/aggregate based on inconsistent row count
T1:  COMMIT
─────────────────────────────────────────────────────────────────

Prevention: SERIALIZABLE (or REPEATABLE_READ in InnoDB with gap locks)

InnoDB gap lock approach:
- REPEATABLE_READ + SELECT locks the GAP between index records
- Prevents INSERTs into the range
- PostgreSQL: REPEATABLE_READ uses snapshot (no phantoms for reads, but write skew possible)
```

### Lost Update (Critical for Interviews)

Two transactions read the same data, then both update it - the second update overwrites the first.

```
Timeline (Classic Lost Update):
─────────────────────────────────────────────────────────────────
T1:  BEGIN
T1:  SELECT balance FROM accounts WHERE id = 1 → 1000
                                T2: BEGIN
                                T2: SELECT balance FROM accounts WHERE id = 1 → 1000
T1:  UPDATE accounts SET balance = 1000 - 200 = 800 WHERE id = 1
T1:  COMMIT ✓
                                T2: UPDATE accounts SET balance = 1000 - 300 = 700 WHERE id = 1
                                T2: COMMIT ✓
                                    ← LOST! T1's -200 is gone. Balance should be 500.
─────────────────────────────────────────────────────────────────
```

**Solutions:**

```java
// Solution 1: Optimistic Locking (@Version)
@Entity
public class Account {
    @Id private Long id;
    @Version private int version;
    private BigDecimal balance;
}
// UPDATE accounts SET balance=800, version=2 WHERE id=1 AND version=1
// T2's UPDATE: WHERE version=1 → 0 rows updated → OptimisticLockException

// Solution 2: Pessimistic Locking (SELECT FOR UPDATE)
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("SELECT a FROM Account a WHERE a.id = :id")
Account findByIdForUpdate(@Param("id") Long id);
// T2 blocks on SELECT until T1 commits

// Solution 3: Atomic Database Operation
@Modifying
@Query("UPDATE Account a SET a.balance = a.balance - :amount WHERE a.id = :id")
int debit(@Param("id") Long id, @Param("amount") BigDecimal amount);
// No read-then-write: single atomic UPDATE avoids the race
```

### Write Skew (Advanced - Serializable Only)

Two transactions read overlapping data, make decisions based on what they read, then write to different rows - violating a cross-row constraint.

```
Scenario: Hospital requires at least 1 doctor on-call at all times.
Currently: Dr. Alice (on_call=true), Dr. Bob (on_call=true)

Timeline:
─────────────────────────────────────────────────────────────────
T1 (Alice wants to leave):
    BEGIN
    SELECT COUNT(*) FROM doctors WHERE on_call = true → 2
    -- "OK, 2 on-call, I can leave (at least 1 remains)"
                                T2 (Bob wants to leave):
                                    BEGIN
                                    SELECT COUNT(*) FROM doctors WHERE on_call = true → 2
                                    -- "OK, 2 on-call, I can leave (at least 1 remains)"
T1: UPDATE doctors SET on_call = false WHERE name = 'Alice'
T1: COMMIT ✓
                                T2: UPDATE doctors SET on_call = false WHERE name = 'Bob'
                                T2: COMMIT ✓
                                    ← VIOLATION! No doctors on call!
─────────────────────────────────────────────────────────────────

Why REPEATABLE_READ doesn't help:
- Both transactions read the SAME snapshot (count=2)
- They write to DIFFERENT rows (no write conflict detected)
- MVCC won't detect this because no single row has a write-write conflict

Solutions:
1. SERIALIZABLE isolation (PostgreSQL SSI detects read-write dependencies)
2. Explicit lock on the rows you READ:
   SELECT * FROM doctors WHERE on_call = true FOR UPDATE;
   (Now T2 blocks until T1 commits, then sees count=1, aborts)
3. Materializing the constraint: add a separate row/table that tracks the invariant
```

### Read Skew

A transaction reads two related pieces of data at different points in time, seeing an inconsistent state.

```
Scenario: x + y must always equal 100. Currently x=50, y=50.

Timeline:
─────────────────────────────────────────────────────────────────
T1:  BEGIN
T1:  SELECT x → 50
                                T2: BEGIN
                                T2: UPDATE x = 25, y = 75  (still sums to 100)
                                T2: COMMIT ✓
T1:  SELECT y → 75  (sees T2's committed change!)
T1:  x + y = 50 + 75 = 125  ← INCONSISTENT READ!
T1:  COMMIT
─────────────────────────────────────────────────────────────────

Prevention: REPEATABLE_READ or higher (T1 would see y=50 from its snapshot)
```

---

## 3. Optimistic Locking Deep Dive

### @Version Mechanics Internally

```java
@Entity
public class Product {
    @Id @GeneratedValue
    private Long id;
    
    @Version
    private int version;  // Hibernate manages this automatically
    
    private String name;
    private BigDecimal price;
}
```

**What Hibernate generates:**

```sql
-- On UPDATE, version is in WHERE clause AND incremented:
UPDATE products 
SET name = ?, price = ?, version = ?  -- version = oldVersion + 1
WHERE id = ? AND version = ?          -- WHERE version = oldVersion

-- If 0 rows affected → StaleObjectStateException (wrapped as OptimisticLockException)
```

### Complete Flow When Conflict Occurs

```
┌─────────────────────────────────────────────────────────────┐
│ Optimistic Lock Failure Flow                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. em.flush() triggers dirty checking                       │
│  2. Product found dirty (price changed)                      │
│  3. EntityUpdateAction scheduled in ActionQueue              │
│  4. Action executes:                                         │
│     UPDATE products SET price=?, version=2                   │
│     WHERE id=1 AND version=1                                 │
│  5. JDBC returns rowsAffected = 0                           │
│  6. Hibernate checks: rowsAffected < expected (1)           │
│  7. Throws StaleObjectStateException                         │
│  8. Spring wraps as OptimisticLockingFailureException        │
│  9. Transaction marked for rollback                          │
│  10. All changes in current persistence context LOST         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Retry Strategy Implementation

```java
@Service
public class ProductService {
    
    private static final int MAX_RETRIES = 3;
    private static final long BASE_DELAY_MS = 100;
    
    @Autowired
    private ProductRepository repository;
    
    public Product updatePrice(Long productId, BigDecimal newPrice) {
        int attempt = 0;
        while (true) {
            try {
                return doUpdatePrice(productId, newPrice);
            } catch (OptimisticLockingFailureException e) {
                attempt++;
                if (attempt >= MAX_RETRIES) {
                    throw new ConflictException(
                        "Failed to update product after " + MAX_RETRIES + " attempts", e);
                }
                // Exponential backoff with jitter
                long delay = BASE_DELAY_MS * (long) Math.pow(2, attempt - 1);
                delay += ThreadLocalRandom.current().nextLong(delay / 2);
                try { Thread.sleep(delay); } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException(ie);
                }
            }
        }
    }
    
    @Transactional
    protected Product doUpdatePrice(Long productId, BigDecimal newPrice) {
        Product product = repository.findById(productId)
            .orElseThrow(() -> new NotFoundException("Product not found"));
        product.setPrice(newPrice);
        return repository.save(product);
        // flush on commit → version check happens here
    }
}
```

### Retry Storms at Scale

```
Problem: 1000 concurrent requests updating same entity

Without backoff:
─────────────────────────────────────────────────────
Time 0:  1000 requests all read version=1
Time 1:  1000 requests all attempt UPDATE WHERE version=1
         → 1 succeeds, 999 fail
Time 2:  999 retry, all read version=2
         → 1 succeeds, 998 fail
Time 3:  998 retry, all read version=3
         → 1 succeeds, 997 fail
...
Total attempts: 1000 + 999 + 998 + ... + 1 = ~500,000 attempts!
─────────────────────────────────────────────────────

Solutions:
1. Exponential backoff + jitter (spread retries over time)
2. Circuit breaker (fail fast after N attempts system-wide)
3. Queue-based serialization (serialize writes for hot entities)
4. Pessimistic lock for known-hot entities
5. Aggregate operations: batch concurrent updates
```

### @OptimisticLocking Strategies

```java
// Default: use @Version column
@Entity
@OptimisticLocking(type = OptimisticLockType.VERSION)
public class Product { ... }

// Use ALL columns in WHERE clause (no @Version needed)
@Entity
@OptimisticLocking(type = OptimisticLockType.ALL)
@DynamicUpdate
public class Product {
    // UPDATE products SET name=? WHERE id=? AND name=? AND price=? AND ...
    // All original values in WHERE clause
}

// Use only DIRTY columns in WHERE clause
@Entity
@OptimisticLocking(type = OptimisticLockType.DIRTY)
@DynamicUpdate
public class Product {
    // UPDATE products SET name='New' WHERE id=1 AND name='Old'
    // Only changed columns in WHERE
    // Allows concurrent updates to DIFFERENT columns without conflict
}
```

### Optimistic Locking with Detached Entities

```java
// User edits a form (entity becomes detached during HTTP request)
// Step 1: Load entity (version = 5)
Product product = productService.findById(1L);
// Send to UI as DTO with version field

// Step 2: User edits and submits (version=5 in form data)
// Entity is DETACHED (not in any persistence context)

// Step 3: Merge back
@Transactional
public Product update(ProductDTO dto) {
    Product managed = repository.findById(dto.getId()).get();
    
    // MANUAL version check for detached scenarios
    if (managed.getVersion() != dto.getVersion()) {
        throw new OptimisticLockException("Entity was modified by another user");
    }
    
    managed.setName(dto.getName());
    managed.setPrice(dto.getPrice());
    return repository.save(managed);
    // Hibernate still does version check on flush
}
```

---

## 4. Pessimistic Locking Deep Dive

### Lock Modes in JPA

```java
// PESSIMISTIC_READ - shared lock (multiple readers OK, blocks writers)
@Lock(LockModeType.PESSIMISTIC_READ)
@Query("SELECT a FROM Account a WHERE a.id = :id")
Account findByIdWithSharedLock(@Param("id") Long id);
// SQL: SELECT ... FROM accounts WHERE id = ? FOR SHARE

// PESSIMISTIC_WRITE - exclusive lock (blocks everyone)
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("SELECT a FROM Account a WHERE a.id = :id")
Account findByIdWithExclusiveLock(@Param("id") Long id);
// SQL: SELECT ... FROM accounts WHERE id = ? FOR UPDATE

// PESSIMISTIC_FORCE_INCREMENT - exclusive lock + increment @Version
@Lock(LockModeType.PESSIMISTIC_FORCE_INCREMENT)
@Query("SELECT a FROM Account a WHERE a.id = :id")
Account findByIdWithForceIncrement(@Param("id") Long id);
// SQL: SELECT ... FOR UPDATE + UPDATE version
// Forces version increment even if entity data doesn't change
// Use: when locking a parent to signal change in aggregate
```

### Lock Timeout Configuration

```java
// Per-query lock timeout
@QueryHints({
    @QueryHint(name = "javax.persistence.lock.timeout", value = "5000")  // 5 seconds
})
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("SELECT a FROM Account a WHERE a.id = :id")
Optional<Account> findByIdForUpdate(@Param("id") Long id);

// NOWAIT - fail immediately if lock not available
@QueryHints({
    @QueryHint(name = "javax.persistence.lock.timeout", value = "0")  // NOWAIT
})

// SKIP LOCKED - skip rows that are locked (for queue-like patterns)
@QueryHints({
    @QueryHint(name = "javax.persistence.lock.timeout", value = "-2")
})
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("SELECT t FROM Task t WHERE t.status = 'PENDING' ORDER BY t.createdAt")
List<Task> findPendingTasksSkipLocked(Pageable pageable);
// SQL: SELECT ... FOR UPDATE SKIP LOCKED
// Perfect for: work queues, job processing, task distribution
```

### SKIP LOCKED Pattern (Work Queue)

```java
@Service
public class TaskProcessingService {
    
    @Transactional
    public Optional<Task> claimNextTask() {
        // SKIP LOCKED: if another worker locked a task, skip it
        List<Task> tasks = taskRepository.findPendingTasksSkipLocked(
            PageRequest.of(0, 1));
        
        if (tasks.isEmpty()) return Optional.empty();
        
        Task task = tasks.get(0);
        task.setStatus(TaskStatus.PROCESSING);
        task.setClaimedBy(getCurrentWorker());
        task.setClaimedAt(Instant.now());
        return Optional.of(task);
    }
}

// Multiple workers can call this concurrently:
// Worker 1: locks task-1, processes it
// Worker 2: skips task-1 (locked), locks task-2
// Worker 3: skips task-1 & task-2, locks task-3
// No contention, no waiting!
```

### When to Use Pessimistic vs Optimistic

```
┌─────────────────────────────────────────────────────────────┐
│ Decision Framework                                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ Use OPTIMISTIC when:                                         │
│ ├── Low contention (conflicts are rare)                      │
│ ├── Read-heavy workload                                      │
│ ├── Short transactions                                       │
│ ├── Retry is acceptable to user                              │
│ ├── No external side effects (email, API calls) in TX       │
│ └── You want maximum concurrency                             │
│                                                               │
│ Use PESSIMISTIC when:                                        │
│ ├── High contention (many concurrent writes to same data)    │
│ ├── Retry cost is high (external side effects in TX)         │
│ ├── Conflict rate > ~5% (retry storms become expensive)      │
│ ├── Operations must not be repeated (payments, inventory)    │
│ ├── You need guaranteed forward progress                     │
│ └── Transaction is short (hold lock briefly)                 │
│                                                               │
│ Use SKIP LOCKED when:                                        │
│ ├── Queue/job processing pattern                             │
│ ├── Multiple workers competing for tasks                     │
│ ├── Don't care about ordering (any available task is fine)   │
│ └── Want zero contention between workers                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Deadlock Scenarios & Prevention

### How Deadlocks Occur with JPA

```
Scenario: Two services updating related entities in different order

T1: Transfer $100 from Account A to Account B
T2: Transfer $50 from Account B to Account A

Timeline:
─────────────────────────────────────────────────────────────────
T1: SELECT * FROM accounts WHERE id = 'A' FOR UPDATE  ← locks A
                    T2: SELECT * FROM accounts WHERE id = 'B' FOR UPDATE  ← locks B
T1: SELECT * FROM accounts WHERE id = 'B' FOR UPDATE  ← BLOCKS (B locked by T2)
                    T2: SELECT * FROM accounts WHERE id = 'A' FOR UPDATE  ← BLOCKS (A locked by T1)
                    
                    ← DEADLOCK! Both waiting for each other.
                    
Database detects deadlock (wait-for graph cycle)
→ One transaction chosen as VICTIM and rolled back
─────────────────────────────────────────────────────────────────
```

### Deadlock from Hibernate Flush Ordering

```
Scenario: Hibernate's automatic flush order can cause unexpected locking

@Entity Order has FK to Customer
@Entity Customer has FK to nothing

T1: Updates Customer #1, then Order #1 (FK to Customer #2)
T2: Updates Customer #2, then Order #2 (FK to Customer #1)

After flush ordering (Hibernate orders by entity type):
T1 flush: UPDATE customers SET ... WHERE id=1  ← locks Customer#1
          UPDATE orders SET ... WHERE id=1      ← needs FK check on Customer#2
T2 flush: UPDATE customers SET ... WHERE id=2  ← locks Customer#2
          UPDATE orders SET ... WHERE id=2      ← needs FK check on Customer#1

If FK constraint checking also acquires shared locks:
T1 holds Customer#1, needs Customer#2
T2 holds Customer#2, needs Customer#1
→ DEADLOCK
```

### Prevention Strategies

```java
// Strategy 1: CONSISTENT LOCK ORDERING
// Always acquire locks in the same order (e.g., by ID ascending)
@Transactional
public void transfer(Long fromId, Long toId, BigDecimal amount) {
    // Always lock lower ID first
    Long firstId = Math.min(fromId, toId);
    Long secondId = Math.max(fromId, toId);
    
    Account first = accountRepository.findByIdForUpdate(firstId);
    Account second = accountRepository.findByIdForUpdate(secondId);
    
    Account from = fromId.equals(firstId) ? first : second;
    Account to = toId.equals(firstId) ? first : second;
    
    from.debit(amount);
    to.credit(amount);
}

// Strategy 2: LOCK TIMEOUT
@QueryHints(@QueryHint(name = "javax.persistence.lock.timeout", value = "3000"))
@Lock(LockModeType.PESSIMISTIC_WRITE)
Optional<Account> findByIdForUpdate(Long id);
// If can't acquire lock in 3s → PessimisticLockException
// Application retries with backoff

// Strategy 3: REDUCING TRANSACTION SCOPE
// Shorter transactions = shorter lock hold time = less deadlock chance
@Transactional
public void processOrder(Long orderId) {
    // DON'T: call external API while holding lock
    Order order = orderRepository.findByIdForUpdate(orderId);
    // externalService.notifyWarehouse(order); ← WRONG: holds lock during HTTP call
    order.setStatus(PROCESSING);
    // Commit releases lock immediately
}
// After commit, make the external call:
// externalService.notifyWarehouse(orderId);

// Strategy 4: TRY-LOCK with NOWAIT
public boolean tryLockAndProcess(Long accountId) {
    try {
        Account account = accountRepository.findByIdNoWait(accountId);
        // Process...
        return true;
    } catch (PessimisticLockException e) {
        // Lock not available - try again later
        return false;
    }
}
```

### Deadlock Detection & Analysis

```sql
-- PostgreSQL: Show current locks
SELECT 
    pg_locks.pid,
    pg_stat_activity.query,
    pg_locks.mode,
    pg_locks.granted,
    pg_class.relname
FROM pg_locks
JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
LEFT JOIN pg_class ON pg_locks.relation = pg_class.oid
WHERE NOT pg_locks.granted;  -- Show WAITING locks

-- PostgreSQL: Detect deadlocks (appears in log)
-- SET deadlock_timeout = '1s';  -- How long to wait before checking for deadlock

-- MySQL: Show InnoDB lock waits
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
SELECT * FROM information_schema.INNODB_LOCKS;
-- Or: SHOW ENGINE INNODB STATUS;  (shows deadlock info)
```

**Reading MySQL deadlock log:**
```
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 5 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 10, query id 100
UPDATE accounts SET balance = 800 WHERE id = 1

*** (2) TRANSACTION:  
TRANSACTION 12346, ACTIVE 3 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 11, query id 101
UPDATE accounts SET balance = 700 WHERE id = 2

*** WE ROLL BACK TRANSACTION (1)  ← Victim chosen by InnoDB
```

---

## 6. Concurrency Patterns with JPA

### Aggregate Locking Pattern

Lock the aggregate root to protect all invariants within the aggregate:

```java
@Entity
public class Order {  // Aggregate Root
    @Id private Long id;
    @Version private int version;
    
    @OneToMany(cascade = ALL, orphanRemoval = true)
    private List<OrderItem> items;
    
    private BigDecimal total;
    
    // Business method that maintains invariant (total = sum of items)
    public void addItem(Product product, int quantity) {
        items.add(new OrderItem(product, quantity));
        this.total = items.stream()
            .map(OrderItem::getSubtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }
}

@Service
public class OrderService {
    
    @Transactional
    public void addItemToOrder(Long orderId, Long productId, int qty) {
        // Locking the Order (root) protects the entire aggregate
        Order order = orderRepository.findByIdForUpdate(orderId);
        Product product = productRepository.findById(productId).get();
        order.addItem(product, qty);
        // Version increment on flush protects against concurrent modification
    }
}
```

### Compare-and-Swap Pattern

```java
@Repository
public interface InventoryRepository extends JpaRepository<Inventory, Long> {
    
    // CAS: only update if current value matches expected
    @Modifying
    @Query("UPDATE Inventory i SET i.quantity = :newQty, i.version = i.version + 1 " +
           "WHERE i.productId = :productId AND i.quantity = :expectedQty")
    int compareAndSwapQuantity(
        @Param("productId") Long productId,
        @Param("expectedQty") int expectedQty,
        @Param("newQty") int newQty
    );
}

@Service
public class InventoryService {
    
    public boolean reserveStock(Long productId, int quantity) {
        int maxAttempts = 5;
        for (int i = 0; i < maxAttempts; i++) {
            Inventory inv = inventoryRepository.findByProductId(productId);
            int current = inv.getQuantity();
            
            if (current < quantity) return false; // Not enough stock
            
            int updated = inventoryRepository.compareAndSwapQuantity(
                productId, current, current - quantity);
            
            if (updated == 1) return true; // CAS succeeded
            // CAS failed: someone else changed quantity, retry
        }
        throw new ConflictException("Could not reserve stock after " + maxAttempts + " attempts");
    }
}
```

### Reservation Pattern (Temporary Lock with Expiration)

```java
@Entity
public class SeatReservation {
    @Id @GeneratedValue
    private Long id;
    
    private Long seatId;
    private Long userId;
    private Instant reservedAt;
    private Instant expiresAt;  // Auto-expire after 10 minutes
    
    @Enumerated(STRING)
    private ReservationStatus status;  // HELD, CONFIRMED, EXPIRED
}

@Service
public class SeatReservationService {
    
    @Transactional
    public SeatReservation holdSeat(Long seatId, Long userId) {
        // Use SKIP LOCKED: if seat is already being reserved, skip it
        // First, expire old reservations
        reservationRepository.expireOldReservations(Instant.now());
        
        // Check if seat is available (no active reservation)
        Optional<SeatReservation> existing = reservationRepository
            .findActiveBySeatId(seatId);
        
        if (existing.isPresent()) {
            throw new SeatUnavailableException("Seat already reserved");
        }
        
        SeatReservation reservation = new SeatReservation();
        reservation.setSeatId(seatId);
        reservation.setUserId(userId);
        reservation.setReservedAt(Instant.now());
        reservation.setExpiresAt(Instant.now().plus(10, ChronoUnit.MINUTES));
        reservation.setStatus(ReservationStatus.HELD);
        
        return reservationRepository.save(reservation);
    }
    
    @Transactional
    public void confirmReservation(Long reservationId, Long userId) {
        SeatReservation reservation = reservationRepository
            .findByIdForUpdate(reservationId);  // Pessimistic lock
        
        if (!reservation.getUserId().equals(userId)) {
            throw new UnauthorizedException();
        }
        if (reservation.getExpiresAt().isBefore(Instant.now())) {
            throw new ReservationExpiredException();
        }
        
        reservation.setStatus(ReservationStatus.CONFIRMED);
    }
}
```

### Offline Optimistic Locking (Long Conversations)

For wizard-style UIs where user edits span multiple HTTP requests:

```java
// DTO carries version to the client
public class ProductEditDTO {
    private Long id;
    private int version;  // Version at the time user started editing
    private String name;
    private BigDecimal price;
}

@RestController
public class ProductController {
    
    @GetMapping("/products/{id}/edit")
    public ProductEditDTO getForEdit(@PathVariable Long id) {
        Product product = productService.findById(id);
        return new ProductEditDTO(
            product.getId(),
            product.getVersion(),  // Send version to client
            product.getName(),
            product.getPrice()
        );
    }
    
    @PutMapping("/products/{id}")
    public ResponseEntity<?> update(@PathVariable Long id, 
                                     @RequestBody ProductEditDTO dto) {
        try {
            Product updated = productService.updateWithVersionCheck(id, dto);
            return ResponseEntity.ok(updated);
        } catch (StaleDataException e) {
            // 409 Conflict: someone else edited this product
            return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of(
                    "message", "Product was modified by another user",
                    "currentVersion", e.getCurrentVersion(),
                    "yourVersion", dto.getVersion()
                ));
        }
    }
}

@Service
public class ProductService {
    
    @Transactional
    public Product updateWithVersionCheck(Long id, ProductEditDTO dto) {
        Product product = productRepository.findById(id)
            .orElseThrow(() -> new NotFoundException("Product not found"));
        
        // Manual version check (entity may have been modified multiple times
        // since user loaded the edit form)
        if (product.getVersion() != dto.getVersion()) {
            throw new StaleDataException(
                "Expected version " + dto.getVersion() + 
                " but found " + product.getVersion(),
                product.getVersion());
        }
        
        product.setName(dto.getName());
        product.setPrice(dto.getPrice());
        return productRepository.save(product);
        // Hibernate's @Version provides additional protection at flush time
    }
}
```

---

## 7. Connection-Level Concurrency

### How Connection Pool Affects Transaction Concurrency

```
┌──────────────────────────────────────────────────────────────┐
│ Connection Pool: Max Size = 10                                │
│                                                                │
│  Concurrent requests: 50                                      │
│  Each transaction holds connection for: ~200ms                │
│                                                                │
│  Throughput = Pool Size / Avg TX Duration                     │
│            = 10 / 0.2s = 50 TPS maximum                      │
│                                                                │
│  If TX duration increases to 500ms (slow query/external call):│
│            = 10 / 0.5s = 20 TPS maximum                      │
│                                                                │
│  Remaining 30 requests: WAITING for connection (queued)       │
│  If wait > connectionTimeout (30s) → SQLException            │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### Timeout Hierarchy

```java
// 1. Connection timeout: how long to wait for pool to provide a connection
spring.datasource.hikari.connection-timeout=30000  // 30 seconds

// 2. Transaction timeout: max duration for the entire transaction
@Transactional(timeout = 10)  // 10 seconds, then rollback
// Sets statement timeout internally

// 3. Query timeout: max duration for a single SQL query
@QueryHints(@QueryHint(name = "org.hibernate.timeout", value = "5"))  // 5 seconds
// or: entityManager.createQuery(...).setHint("javax.persistence.query.timeout", 5000);

// 4. Lock timeout: how long to wait for a pessimistic lock
@QueryHints(@QueryHint(name = "javax.persistence.lock.timeout", value = "3000"))

// 5. Socket timeout: TCP level (driver configuration)
spring.datasource.url=jdbc:postgresql://host/db?socketTimeout=60
```

### Connection Starvation Under Contention

```
Scenario: Long-running transaction holds connections

Request flow with pessimistic locking:
─────────────────────────────────────────────────────────
Thread-1: Get connection, SELECT FOR UPDATE (row A)
          Process (5 seconds)...
          Still holding connection + lock...
          
Thread-2: Get connection, SELECT FOR UPDATE (row A)
          BLOCKED on lock (waiting for Thread-1)
          Still holding connection (doing nothing)!
          
Thread-3..10: Get connections, also blocked on lock
              ALL pool connections now occupied!

Thread-11: Needs connection → TIMEOUT (pool exhausted)
           Even for completely unrelated queries!
─────────────────────────────────────────────────────────

Solution: Lock timeout + smaller pool + shorter transactions
```

---

## 8. Real-World Architect Scenarios

### Scenario 1: Inventory Counter with 1000 Concurrent Users

**Problem**: Flash sale, 1000 users trying to buy the same product simultaneously.

```java
// WRONG: Classic lost update
@Transactional
public void purchase(Long productId) {
    Product p = productRepo.findById(productId).get();
    if (p.getStock() > 0) {
        p.setStock(p.getStock() - 1);  // Race condition!
    }
}

// SOLUTION 1: Pessimistic lock + SKIP LOCKED for throughput
@Transactional
public boolean purchase(Long productId) {
    // SELECT ... FOR UPDATE NOWAIT
    try {
        Product p = productRepo.findByIdForUpdateNoWait(productId);
        if (p.getStock() <= 0) return false;
        p.setStock(p.getStock() - 1);
        return true;
    } catch (PessimisticLockException e) {
        return false; // Tell user to retry
    }
}

// SOLUTION 2: Atomic UPDATE (no read needed)
@Modifying
@Query("UPDATE Product p SET p.stock = p.stock - 1 " +
       "WHERE p.id = :id AND p.stock > 0")
int decrementStock(@Param("id") Long productId);
// Returns 1 if successful, 0 if out of stock
// Single atomic operation, no race condition, maximum throughput

// SOLUTION 3: Redis for hot counter + async DB sync
// Use Redis DECR for real-time stock, periodically sync to DB
// Handles extreme concurrency (100K+ TPS)
```

### Scenario 2: Bank Transfer - No Double-Spend

```java
@Service
public class TransferService {
    
    @Transactional(isolation = Isolation.READ_COMMITTED)
    public TransferResult transfer(Long fromId, Long toId, BigDecimal amount) {
        // Lock ordering: always lock lower ID first to prevent deadlock
        Long firstLock = Math.min(fromId, toId);
        Long secondLock = Math.max(fromId, toId);
        
        Account first = accountRepo.findByIdForUpdate(firstLock);
        Account second = accountRepo.findByIdForUpdate(secondLock);
        
        Account from = fromId.equals(firstLock) ? first : second;
        Account to = toId.equals(firstLock) ? first : second;
        
        if (from.getBalance().compareTo(amount) < 0) {
            throw new InsufficientFundsException();
        }
        
        from.setBalance(from.getBalance().subtract(amount));
        to.setBalance(to.getBalance().add(amount));
        
        // Create audit record within same transaction
        Transfer transfer = new Transfer(fromId, toId, amount, Instant.now());
        transferRepo.save(transfer);
        
        return TransferResult.success(transfer.getId());
    }
}
```

### Scenario 3: Ticket Booking - Prevent Double-Booking

```java
@Service
public class BookingService {
    
    @Transactional
    public Booking bookSeat(Long eventId, String seatNumber, Long userId) {
        // Use unique constraint + pessimistic lock
        
        // Check if seat already booked (with lock to prevent race)
        Optional<Booking> existing = bookingRepo
            .findByEventIdAndSeatNumberForUpdate(eventId, seatNumber);
        
        if (existing.isPresent()) {
            throw new SeatAlreadyBookedException(seatNumber);
        }
        
        Booking booking = new Booking();
        booking.setEventId(eventId);
        booking.setSeatNumber(seatNumber);
        booking.setUserId(userId);
        booking.setBookedAt(Instant.now());
        booking.setStatus(BookingStatus.CONFIRMED);
        
        try {
            return bookingRepo.save(booking);
        } catch (DataIntegrityViolationException e) {
            // Unique constraint (event_id, seat_number) catches any race condition
            throw new SeatAlreadyBookedException(seatNumber);
        }
    }
}

// Entity with unique constraint as safety net:
@Entity
@Table(uniqueConstraints = @UniqueConstraint(
    columnNames = {"event_id", "seat_number"}))
public class Booking { ... }
```

### Scenario 4: Auction - Last-Second Bid Consistency

```java
@Entity
public class Auction {
    @Id private Long id;
    @Version private int version;
    private BigDecimal currentBid;
    private Long currentBidderId;
    private Instant endsAt;
}

@Service
public class AuctionService {
    
    @Transactional
    public BidResult placeBid(Long auctionId, Long userId, BigDecimal bidAmount) {
        // Pessimistic lock: critical for auction integrity
        Auction auction = auctionRepo.findByIdForUpdate(auctionId);
        
        // Validate
        if (Instant.now().isAfter(auction.getEndsAt())) {
            return BidResult.auctionEnded();
        }
        if (bidAmount.compareTo(auction.getCurrentBid()) <= 0) {
            return BidResult.bidTooLow(auction.getCurrentBid());
        }
        
        // Record bid history
        BidHistory bid = new BidHistory(auctionId, userId, bidAmount, Instant.now());
        bidHistoryRepo.save(bid);
        
        // Update auction
        auction.setCurrentBid(bidAmount);
        auction.setCurrentBidderId(userId);
        
        // Extend auction if bid in last 2 minutes (anti-sniping)
        if (auction.getEndsAt().minus(2, ChronoUnit.MINUTES).isBefore(Instant.now())) {
            auction.setEndsAt(auction.getEndsAt().plus(2, ChronoUnit.MINUTES));
        }
        
        return BidResult.success(bidAmount);
    }
}
```

---

## 9. Key Interview Talking Points

### "How would you handle high-contention writes in your system?"

**Structured answer framework:**

1. **Characterize the contention**: Is it on same row? Same table? How many concurrent writers?
2. **Choose strategy based on conflict rate**:
   - < 1% conflicts: Optimistic locking (simple, high throughput)
   - 1-10% conflicts: Optimistic with retry + exponential backoff
   - > 10% conflicts: Pessimistic locking or queue-based serialization
3. **Consider atomic operations**: Can the UPDATE be expressed as single SQL? (SET x = x - 1)
4. **Hot spot mitigation**: SKIP LOCKED for queue patterns, sharding for distribution
5. **Monitoring**: Track optimistic lock failure rate, deadlock frequency, lock wait times

### "Explain the trade-offs between optimistic and pessimistic locking"

| Dimension | Optimistic | Pessimistic |
|-----------|-----------|-------------|
| Throughput (low contention) | Higher | Lower (lock overhead) |
| Throughput (high contention) | Lower (retry storms) | Higher (serialized, no retries) |
| Latency (no conflict) | Lower | Higher (lock acquisition) |
| Latency (with conflict) | Higher (retry + backoff) | Lower (just waits) |
| Connection hold time | Short | Longer (held during lock wait) |
| Deadlock risk | None | Yes |
| Retry logic needed | Yes | No (but timeout handling needed) |
| External side effects | Safe (no duplicates) | Safe (held in transaction) |
| Scalability | Better at scale | Connection pool limits |

### "How do you prevent deadlocks in a microservices architecture?"

1. **Within a service**: Consistent lock ordering, lock timeouts, minimized lock scope
2. **Across services**: No distributed locks via DB; use Saga pattern instead
3. **Database level**: Index properly (row locks not table locks), short transactions
4. **Monitoring**: Deadlock rate alerts, automatic retry on deadlock victim selection
5. **Design**: Aggregate boundaries reduce cross-entity locking needs
