# Production Incident Debugging Scenarios (Staff Engineer / Architect Level)

## Essential Diagnostic Tools Reference

### Thread Dump Analysis
```bash
# Take thread dump
jcmd <pid> Thread.print > threaddump_$(date +%s).txt

# Take 3 dumps 10 seconds apart (to identify stuck threads)
for i in 1 2 3; do jcmd <pid> Thread.print > td_$i.txt; sleep 10; done

# GC info
jcmd <pid> GC.heap_info
jcmd <pid> VM.native_memory summary

# Heap dump
jcmd <pid> GC.heap_dump /tmp/heap.hprof
```

### HikariCP JMX Monitoring
```java
// Programmatic access
HikariPoolMXBean poolMXBean = hikariDataSource.getHikariPoolMXBean();
poolMXBean.getTotalConnections();
poolMXBean.getActiveConnections();
poolMXBean.getIdleConnections();
poolMXBean.getThreadsAwaitingConnection();
```

```bash
# JMX via jconsole/jmxterm
echo "get -b com.zaxxer.hikari:type=Pool\ (HikariPool-1) TotalConnections" | java -jar jmxterm.jar
echo "get -b com.zaxxer.hikari:type=Pool\ (HikariPool-1) ActiveConnections" | java -jar jmxterm.jar
echo "get -b com.zaxxer.hikari:type=Pool\ (HikariPool-1) ThreadsAwaitingConnection" | java -jar jmxterm.jar
```

### PostgreSQL Diagnostic Queries
```sql
-- Active connections and what they're doing
SELECT pid, state, wait_event_type, wait_event, query_start, 
       now() - query_start AS duration, query
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY duration DESC;

-- Lock contention
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Table bloat and vacuum status
SELECT schemaname, relname, n_live_tup, n_dead_tup, 
       last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
FROM pg_stat_user_tables 
ORDER BY n_dead_tup DESC LIMIT 20;
```

### Hibernate Statistics
```java
// Enable in application.yml
// spring.jpa.properties.hibernate.generate_statistics=true

Statistics stats = entityManagerFactory.unwrap(SessionFactory.class).getStatistics();
stats.getQueryExecutionCount();
stats.getQueryExecutionMaxTime();
stats.getEntityLoadCount();
stats.getSecondLevelCacheHitCount();
stats.getSecondLevelCacheMissCount();
stats.getCollectionLoadCount();
```

---

## Incident 1: Connection Pool Exhaustion

### Alert/Symptoms

```
ALERT: HikariPool-1 - Connection is not available, request timed out after 30000ms
ERROR: o.h.e.jdbc.spi.SqlExceptionHelper - HikariPool-1 - Connection is not available

Grafana Dashboard:
- hikaricp_connections_active: 10/10 (maxed out)
- hikaricp_connections_pending: 47 (threads waiting)
- http_server_requests_seconds_p99: jumped from 200ms to 35s
- All API endpoints affected, not just slow ones
```

### Investigation Steps

**Step 1: Confirm pool exhaustion**
```bash
# Check HikariCP metrics via actuator
curl http://localhost:8080/actuator/metrics/hikaricp.connections.active
# Returns: {"measurements":[{"value":10.0}]}

curl http://localhost:8080/actuator/metrics/hikaricp.connections.pending
# Returns: {"measurements":[{"value":47.0}]}
```

**Step 2: Thread dump to identify what's holding connections**
```bash
jcmd $(pgrep -f 'myapp.jar') Thread.print > /tmp/td1.txt

# Look for pattern: threads in RUNNABLE state doing HTTP I/O while holding DB connection
grep -A 30 "RUNNABLE" /tmp/td1.txt | grep -B 5 "java.net.SocketInputStream.read"
```

**Step 3: Identify the pattern in thread dump**
```
"http-nio-8080-exec-15" #78 daemon prio=5 os_prio=0 tid=0x... nid=0x... runnable
   java.lang.Thread.State: RUNNABLE
        at java.net.SocketInputStream.socketRead0(Native Method)
        at java.net.SocketInputStream.read(SocketInputStream.java:152)
        at okhttp3.internal.http1.Http1ExchangeCodec...
        at com.myapp.service.OrderService.createOrder(OrderService.java:45)
        at com.myapp.controller.OrderController.create(OrderController.java:28)
        ...
        at org.springframework.orm.jpa.support.OpenEntityManagerInViewInterceptor.preHandle(...)
```

Key observation: Thread is doing HTTP I/O (SocketInputStream.read) but the call stack shows `OpenEntityManagerInViewInterceptor` opened an EntityManager (and acquired a DB connection) at the start of the request.

**Step 4: Check database side**
```sql
SELECT count(*), state FROM pg_stat_activity 
WHERE datname = 'mydb' GROUP BY state;
-- Result: 10 idle connections (held by app but not executing queries)

SELECT pid, state, query_start, now() - query_start as idle_time
FROM pg_stat_activity 
WHERE state = 'idle in transaction'
ORDER BY idle_time DESC;
-- Shows connections idle for 3-5 seconds (duration of external API call)
```

### Root Cause

**Open Session in View (OSIV)** is enabled by default in Spring Boot (`spring.jpa.open-in-view=true`). This opens an EntityManager (and acquires a DB connection) at the start of every HTTP request and holds it until the response is sent.

The `OrderController.create()` endpoint:
1. Loads order data from DB (needs connection) — 5ms
2. Calls external payment API — **3-5 seconds** (connection held idle)
3. Calls external notification API — **1-2 seconds** (connection still held)
4. Saves result to DB — 10ms

With pool size of 10 and ~15 concurrent requests doing 5s of external I/O each, the pool is permanently exhausted.

```java
// The problematic code
@RestController
public class OrderController {
    
    @PostMapping("/orders")
    public OrderResponse createOrder(@RequestBody OrderRequest request) {
        // OSIV already acquired a connection before this method executes
        
        Order order = orderService.save(request);  // Quick DB operation
        
        // Connection is STILL held during these slow calls:
        PaymentResult payment = paymentClient.charge(order);  // 3-5 seconds
        notificationClient.send(order);  // 1-2 seconds
        
        return OrderResponse.from(order);
        // Connection released only after response is written
    }
}
```

### Immediate Fix

```bash
# Add to application.yml or as environment variable
SPRING_JPA_OPEN_IN_VIEW=false

# Restart with rolling deployment
kubectl rollout restart deployment/order-service
```

### Permanent Fix

```java
// 1. Disable OSIV
// application.yml
spring:
  jpa:
    open-in-view: false

// 2. Restructure the service to release connection before external calls
@Service
public class OrderService {
    
    @Transactional
    public Order createAndPersistOrder(OrderRequest request) {
        // DB operations only - connection acquired and released here
        Order order = new Order(request);
        return orderRepository.save(order);
    }
}

@Service
public class OrderOrchestrator {
    
    private final OrderService orderService;
    private final PaymentClient paymentClient;
    private final NotificationClient notificationClient;
    
    // No @Transactional here - no connection held
    public OrderResponse processOrder(OrderRequest request) {
        // Step 1: DB work (connection acquired and released)
        Order order = orderService.createAndPersistOrder(request);
        
        // Step 2: External calls (NO connection held)
        PaymentResult payment = paymentClient.charge(order);
        notificationClient.send(order);
        
        // Step 3: Update with payment info (connection acquired and released)
        orderService.updatePaymentStatus(order.getId(), payment);
        
        return OrderResponse.from(order);
    }
}

// 3. Configure connection pool with leak detection
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 5000
      leak-detection-threshold: 10000  # Log warning if connection held > 10s
```

### Prevention

1. **Disable OSIV in all projects** — add to company Spring Boot starter
2. **Add HikariCP alerts**: alert if `pending > 0` for more than 30 seconds
3. **Architectural rule**: External HTTP calls MUST NOT happen inside a transaction or while holding a DB connection
4. **Connection pool sizing**: `pool_size = (core_count * 2) + spindle_count` — don't blindly set to 100
5. **Load testing**: Run soak tests with external API latency injection (Toxiproxy) to catch this before production

---

## Incident 2: Memory Leak — OOM After 48 Hours

### Alert/Symptoms

```
ALERT: Pod order-service-7d4f8b restarted (OOMKilled)
ALERT: JVM heap usage > 90% for 15 minutes
ALERT: GC pause time > 5 seconds (Full GC)

Grafana:
- jvm_memory_used_bytes{area="heap"}: steady upward trend over 48h
- jvm_gc_pause_seconds_max: increasing from 100ms to 5s
- Pod restarts: 3 in last 24 hours
- Sawtooth pattern in Old Gen: floor rises with each cycle
```

### Investigation Steps

**Step 1: Confirm memory leak pattern**
```bash
# Check GC logs
jcmd <pid> VM.info | grep -i "heap"
jcmd <pid> GC.heap_info

# Output shows Old Gen nearly full:
# PSPermGen      total 524288K, used 520192K
# PSOldGen       total 2097152K, used 2045000K  <-- almost full
```

**Step 2: Take heap dump before OOM**
```bash
# Enable automatic heap dump on OOM (should be in startup flags)
# -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heap.hprof

# Manual heap dump
jcmd <pid> GC.heap_dump /tmp/heap_$(date +%s).hprof

# Download from pod
kubectl cp order-service-pod:/tmp/heap_1234.hprof ./heap.hprof
```

**Step 3: Analyze with Eclipse MAT or VisualVM**
```
Leak Suspects Report:
- 1 instance of "org.hibernate.internal.SessionImpl" retains 1.2 GB
  - Referenced by Thread "scheduling-1" via ThreadLocal
  - Contains 847,000 entity instances in PersistenceContext
  
Dominator Tree:
  SessionImpl (1.2 GB)
    └── StatefulPersistenceContext (1.1 GB)
        └── Map<EntityKey, Object> entitiesByKey (847,000 entries)
            └── Order entities
            └── OrderItem entities
            └── Customer entities
```

**Step 4: Identify the culprit code path**
```bash
# Check which thread holds the session
grep -A 20 "scheduling-1" /tmp/threaddump.txt
```

```
"scheduling-1" #45 prio=5 tid=0x... nid=0x... waiting
   at com.myapp.job.DailyReportJob.generateReport(DailyReportJob.java:34)
```

### Root Cause

**Scenario A: Scheduled job with @Transactional accumulating entities**

```java
@Component
public class DailyReportJob {
    
    @Scheduled(cron = "0 0 2 * * *")  // Runs at 2 AM
    @Transactional  // ONE transaction for entire job
    public void generateReport() {
        LocalDate start = LocalDate.now().minusDays(30);
        
        // Processes 500K+ orders in a single persistence context
        List<Order> orders = orderRepository.findByCreatedAfter(start);
        
        for (Order order : orders) {
            // Each access loads lazy collections INTO the persistence context
            ReportLine line = new ReportLine();
            line.setTotal(order.getItems().stream()  // lazy load - entities cached
                .mapToDouble(OrderItem::getPrice)
                .sum());
            line.setCustomerName(order.getCustomer().getName());  // another lazy load
            reportLines.add(line);
        }
        // All 500K orders + items + customers are in the persistence context
        // GC cannot reclaim them until transaction commits
    }
}
```

**Scenario B: ThreadLocal EntityManager not cleared in filter**

```java
@Component
public class AuditFilter extends OncePerRequestFilter {
    
    @PersistenceContext
    private EntityManager em;  // Injected - but in a Filter this is dangerous
    
    private static final ThreadLocal<EntityManager> AUDIT_EM = new ThreadLocal<>();
    
    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, 
                                     FilterChain chain) throws Exception {
        // Creates a new EntityManager and stores in ThreadLocal
        EntityManager auditEm = emf.createEntityManager();
        AUDIT_EM.set(auditEm);
        
        try {
            chain.doFilter(req, res);
        } finally {
            // BUG: If exception occurs before this, or if this code is missing:
            // AUDIT_EM.remove();  // <-- MISSING! ThreadLocal never cleared
            // auditEm.close();    // <-- MISSING! EntityManager never closed
        }
    }
}
```

### Immediate Fix

```bash
# Restart the affected pod
kubectl delete pod order-service-7d4f8b

# If scheduled job is running, kill it
# Temporarily disable the job via feature flag or config
kubectl set env deployment/order-service REPORT_JOB_ENABLED=false
```

### Permanent Fix

**For Scenario A (Scheduled Job):**
```java
@Component
public class DailyReportJob {
    
    private final EntityManagerFactory emf;
    private final TransactionTemplate txTemplate;
    
    @Scheduled(cron = "0 0 2 * * *")
    public void generateReport() {
        LocalDate start = LocalDate.now().minusDays(30);
        
        // Use pagination/streaming with stateless session
        int pageSize = 500;
        int page = 0;
        List<Order> batch;
        
        do {
            batch = processPage(start, page, pageSize);
            page++;
        } while (!batch.isEmpty());
    }
    
    // Each page gets its own transaction - persistence context is cleared after each
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public List<Order> processPage(LocalDate start, int page, int size) {
        List<Order> orders = orderRepository.findByCreatedAfter(
            start, PageRequest.of(page, size));
        
        for (Order order : orders) {
            processOrderForReport(order);
        }
        
        return orders;
        // Transaction commits, persistence context cleared, GC can reclaim
    }
    
    // Even better: use a StatelessSession for read-only reporting
    public void generateReportStateless() {
        StatelessSession session = emf.unwrap(SessionFactory.class).openStatelessSession();
        try {
            ScrollableResults results = session.createQuery(
                "SELECT o FROM Order o JOIN FETCH o.items WHERE o.created > :start", Order.class)
                .setParameter("start", start)
                .setFetchSize(500)
                .scroll(ScrollMode.FORWARD_ONLY);
            
            while (results.next()) {
                Order order = (Order) results.get(0);
                processOrderForReport(order);
                // No persistence context - entities are immediately GC-eligible
            }
        } finally {
            session.close();
        }
    }
}
```

**For Scenario B (ThreadLocal leak):**
```java
@Component
public class AuditFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, 
                                     FilterChain chain) throws Exception {
        EntityManager auditEm = emf.createEntityManager();
        AuditContext.set(auditEm);
        
        try {
            chain.doFilter(req, res);
        } finally {
            // ALWAYS clean up in finally block
            try {
                EntityManager em = AuditContext.get();
                if (em != null && em.isOpen()) {
                    em.close();
                }
            } finally {
                AuditContext.remove();  // CRITICAL: always remove ThreadLocal
            }
        }
    }
}

// Better approach: use request-scoped bean instead of ThreadLocal
@Bean
@RequestScope
public AuditContext auditContext() {
    return new AuditContext();
}
```

### Prevention

1. **JVM flags in all deployments**: `-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/`
2. **Alert on heap growth trend**: if Old Gen floor rises for 3 consecutive GC cycles
3. **Batch jobs MUST use pagination** — enforce via code review checklist
4. **ThreadLocal audit**: grep codebase for `ThreadLocal` — each must have a matching `remove()` in a `finally` block
5. **Load test scheduled jobs**: run them against prod-sized datasets in staging
6. **Use `entityManager.clear()` periodically** in long-running transactions

---

## Incident 3: Sudden Query Plan Regression

### Alert/Symptoms

```
ALERT: p99 latency for GET /api/products jumped from 15ms to 12 seconds
ALERT: PostgreSQL CPU at 95%
ALERT: Disk I/O reads spiked 50x

Grafana:
- Specific endpoint affected: product search
- Database CPU: 95%
- Sequential scan count: spiked
- Index scan count: dropped to 0 for products table
- No deployment in last 24 hours
```

### Investigation Steps

**Step 1: Identify the slow query**
```sql
-- Find current slow queries
SELECT pid, now() - query_start AS duration, query, state
FROM pg_stat_activity 
WHERE state = 'active' AND now() - query_start > interval '1 second'
ORDER BY duration DESC;

-- Check pg_stat_statements for recent regression
SELECT query, calls, mean_exec_time, stddev_exec_time,
       rows, shared_blks_hit, shared_blks_read
FROM pg_stat_statements 
WHERE query LIKE '%products%'
ORDER BY mean_exec_time DESC LIMIT 10;
```

**Step 2: Check the query plan**
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM products 
WHERE category_id = 5 AND status = 'ACTIVE' 
AND created_at > '2024-01-01'
ORDER BY popularity DESC LIMIT 20;

-- Output shows:
-- Seq Scan on products  (cost=0.00..450000.00 rows=1 width=256) (actual time=0.1..11543.2 rows=20)
--   Filter: ((category_id = 5) AND (status = 'ACTIVE') AND (created_at > '2024-01-01'))
--   Rows Removed by Filter: 4999980
--   Buffers: shared read=125000   <-- reading entire table from disk
```

**Step 3: Check table statistics and vacuum status**
```sql
-- Check when stats were last gathered
SELECT schemaname, relname, n_live_tup, n_dead_tup, 
       last_vacuum, last_autovacuum, last_analyze, last_autoanalyze,
       n_mod_since_analyze
FROM pg_stat_user_tables WHERE relname = 'products';

-- Output:
-- n_live_tup: 5000000
-- n_dead_tup: 2500000  <-- huge number of dead tuples!
-- last_autoanalyze: 2024-01-15 (3 weeks ago!)
-- n_mod_since_analyze: 3000000  <-- 3M modifications since last analyze

-- Check if the index exists
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'products';
-- idx_products_category_status_created EXISTS - so it's not a missing index

-- Check planner's statistics estimate vs reality
SELECT * FROM pg_stats 
WHERE tablename = 'products' AND attname = 'category_id';
-- n_distinct shows old values, histogram is stale
```

**Step 4: Understand why autovacuum didn't run**
```sql
-- Check autovacuum settings
SHOW autovacuum_vacuum_scale_factor;  -- 0.2 (default)
SHOW autovacuum_analyze_scale_factor;  -- 0.1 (default)

-- For 5M row table, analyze triggers at 500K modifications (10%)
-- But we have 3M modifications - why didn't it trigger?

-- Check if autovacuum workers are saturated
SELECT * FROM pg_stat_progress_vacuum;

-- Check if table was locked (DDL or long transaction blocking vacuum)
SELECT locktype, relation::regclass, mode, granted
FROM pg_locks WHERE relation = 'products'::regclass;
```

### Root Cause

A combination of factors:
1. A bulk data import job loaded 2M new products 3 days ago
2. Autovacuum was blocked by a long-running analytics query holding a `SHARE` lock (from a reporting system that ran `pg_dump` with `--lock-wait-timeout=0`)
3. Table statistics became stale — the planner thought `category_id = 5` had 1 row (old stats) but actually had 500K rows
4. With stale stats, the planner chose a seq scan thinking the filter was highly selective
5. The index `idx_products_category_status_created` was ignored because cost estimates were wrong

### Immediate Fix

```sql
-- Force analyze to update statistics immediately
ANALYZE products;

-- Verify plan is correct now
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM products 
WHERE category_id = 5 AND status = 'ACTIVE' 
AND created_at > '2024-01-01'
ORDER BY popularity DESC LIMIT 20;

-- Should now show:
-- Index Scan using idx_products_category_status_created on products
--   (cost=0.56..150.00 rows=500000 width=256) (actual time=0.05..0.8 rows=20)

-- If immediate relief needed before ANALYZE completes:
-- Force index usage temporarily
SET enable_seqscan = off;  -- Session-level only! Never set globally
```

### Permanent Fix

```sql
-- 1. Tune autovacuum for high-churn tables
ALTER TABLE products SET (
    autovacuum_vacuum_scale_factor = 0.01,      -- vacuum at 1% dead tuples
    autovacuum_analyze_scale_factor = 0.01,     -- analyze at 1% modifications
    autovacuum_vacuum_cost_delay = 2            -- faster vacuum
);

-- 2. Add monitoring for stale statistics
-- Alert when n_mod_since_analyze > 10% of n_live_tup

-- 3. Schedule explicit ANALYZE after bulk operations
```

```java
// In bulk import job - always analyze after large imports
@Service
public class ProductImportService {
    
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    @Transactional
    public void bulkImport(List<Product> products) {
        // ... batch insert logic ...
    }
    
    // Called after import completes
    public void refreshStatistics() {
        jdbcTemplate.execute("ANALYZE products");
    }
}
```

### Prevention

1. **Monitor `n_mod_since_analyze`** — alert if > 5% of table size without analyze
2. **Tune autovacuum per-table** for high-churn tables
3. **Never run long-running queries on primary** — use read replicas for analytics
4. **After bulk operations, always run ANALYZE**
5. **Set `log_min_duration_statement = 1000`** to catch sudden query regressions
6. **Use `pg_stat_statements` to track query performance over time** — alert on 10x regression

---

## Incident 4: Duplicate Data / Double-Processing

### Alert/Symptoms

```
ALERT: Customer support tickets spike - "charged twice for order"
ALERT: Anomaly detection - order_payments table insert rate 2x normal

Investigation reveals:
- 847 orders processed twice in 2-hour window
- Payment gateway shows duplicate charges
- All duplicates occurred during a period of elevated network latency
- Client logs show: "timeout after 30s, retrying..."
```

### Investigation Steps

**Step 1: Identify duplicate records**
```sql
-- Find duplicate orders
SELECT customer_id, product_id, amount, COUNT(*) as cnt,
       MIN(created_at) as first, MAX(created_at) as last,
       MAX(created_at) - MIN(created_at) as gap
FROM orders 
WHERE created_at > now() - interval '4 hours'
GROUP BY customer_id, product_id, amount
HAVING COUNT(*) > 1
ORDER BY cnt DESC;

-- Gap between duplicates is 30-35 seconds (timeout + retry delay)
```

**Step 2: Check application logs for retry patterns**
```bash
# Look for timeout-then-retry pattern
kubectl logs -l app=order-service --since=4h | grep -A 2 "timeout\|retry\|duplicate"

# Pattern found:
# 14:23:01 OrderController: Processing order request-id=abc-123
# 14:23:31 WARN HttpClient: Request timeout after 30s for payment-service
# 14:23:32 OrderController: Processing order request-id=abc-123  <-- SAME request retried
```

**Step 3: Check if idempotency handling exists**
```bash
# Search for idempotency key handling
grep -r "idempotency\|idempotent\|request.id\|X-Idempotency" src/
# Nothing found - no idempotency mechanism exists
```

**Step 4: Trace the duplicate execution**
```sql
-- Check if unique constraint exists
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'orders';
-- Only PK constraint on id column - no business key uniqueness
```

### Root Cause

The order creation endpoint has **no idempotency protection**:

```java
// PROBLEMATIC: No idempotency handling
@RestController
public class OrderController {
    
    @PostMapping("/orders")
    @Transactional
    public ResponseEntity<OrderResponse> createOrder(@RequestBody OrderRequest request) {
        // No check if this request was already processed
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setAmount(request.getAmount());
        orderRepository.save(order);
        
        // Payment call takes 5-10s during degraded conditions
        PaymentResult result = paymentClient.charge(order);  // Succeeds but response times out
        
        order.setPaymentId(result.getId());
        orderRepository.save(order);
        
        return ResponseEntity.ok(OrderResponse.from(order));
    }
}
```

The sequence:
1. Client sends POST /orders with `Idempotency-Key: abc-123`
2. Server processes order, charges payment gateway (succeeds in 25s)
3. Response takes 30s total → client timeout at 30s
4. Client doesn't receive response, assumes failure, retries
5. Server processes the SAME order again — new row, new payment charge
6. Client receives success for the retry

### Immediate Fix

```sql
-- Refund duplicate charges (automated script)
WITH duplicates AS (
    SELECT id, customer_id, amount,
           ROW_NUMBER() OVER (
               PARTITION BY customer_id, product_id, amount, 
               date_trunc('minute', created_at)
               ORDER BY created_at
           ) as rn
    FROM orders 
    WHERE created_at > now() - interval '4 hours'
)
UPDATE orders SET status = 'REFUND_PENDING'
WHERE id IN (SELECT id FROM duplicates WHERE rn > 1);

-- Trigger refunds for flagged orders
```

### Permanent Fix

```java
// 1. Create idempotency key table
@Entity
@Table(name = "idempotency_keys")
public class IdempotencyRecord {
    @Id
    private String key;
    
    @Column(nullable = false)
    private String responseBody;
    
    @Column(nullable = false)
    private int responseStatus;
    
    @Column(nullable = false)
    private Instant createdAt;
    
    @Column(nullable = false)
    private Instant expiresAt;
}

// 2. Idempotency filter/interceptor
@Component
public class IdempotencyInterceptor implements HandlerInterceptor {
    
    private final IdempotencyRepository idempotencyRepo;
    
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response,
                            Object handler) throws Exception {
        if (!"POST".equals(request.getMethod()) && !"PUT".equals(request.getMethod())) {
            return true;
        }
        
        String idempotencyKey = request.getHeader("Idempotency-Key");
        if (idempotencyKey == null) {
            response.sendError(400, "Idempotency-Key header required for POST/PUT");
            return false;
        }
        
        Optional<IdempotencyRecord> existing = idempotencyRepo.findById(idempotencyKey);
        if (existing.isPresent()) {
            IdempotencyRecord record = existing.get();
            response.setStatus(record.getResponseStatus());
            response.getWriter().write(record.getResponseBody());
            response.setHeader("X-Idempotent-Replayed", "true");
            return false;  // Don't process again
        }
        
        // Try to acquire lock on this key
        try {
            idempotencyRepo.insertWithLock(idempotencyKey);  // INSERT with status=PROCESSING
        } catch (DataIntegrityViolationException e) {
            // Another request is processing this key - return 409
            response.sendError(409, "Request is being processed");
            return false;
        }
        
        return true;
    }
}

// 3. Also add database-level protection
@Entity
@Table(name = "orders", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"idempotency_key"})
})
public class Order {
    @Column(name = "idempotency_key", unique = true)
    private String idempotencyKey;
}
```

### Prevention

1. **All mutating endpoints MUST accept and enforce idempotency keys**
2. **Database unique constraints on business keys** (not just surrogate keys)
3. **Client libraries must generate idempotency keys** before first attempt
4. **Payment operations must use payment gateway's built-in idempotency** (Stripe has this)
5. **Outbox pattern** for critical operations — write intent to DB, process asynchronously
6. **Set appropriate client timeouts** — if processing takes 30s, timeout should be 45s

---

## Incident 5: Deadlock Storm During Batch + OLTP

### Alert/Symptoms

```
ALERT: org.hibernate.exception.LockAcquisitionException rate > 50/min
ALERT: PostgreSQL deadlocks_detected: 127 in 5 minutes
ALERT: p99 latency for PUT /api/inventory spike to 30s
ALERT: Batch job "inventory-reconciliation" running concurrent with peak traffic

Application logs:
ERROR: could not execute statement; SQL [n/a]; nested exception is 
org.hibernate.exception.LockAcquisitionException: could not execute statement
Caused by: org.postgresql.util.PSQLException: ERROR: deadlock detected
  Detail: Process 12345 waits for ShareLock on transaction 67890; blocked by process 11111.
  Process 11111 waits for ShareLock on transaction 12345; blocked by process 12345.
```

### Investigation Steps

**Step 1: Check PostgreSQL deadlock details**
```sql
-- View recent deadlocks (requires log_lock_waits = on)
SELECT * FROM pg_stat_database WHERE datname = 'mydb';
-- deadlocks: 127 (was 0 yesterday)

-- Current lock contention
SELECT l.pid, l.locktype, l.mode, l.granted, l.relation::regclass,
       a.query, a.state, a.application_name
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation = 'inventory'::regclass
ORDER BY l.granted, l.pid;
```

**Step 2: Identify the two contending workloads**
```sql
-- Find the batch job process
SELECT pid, query, application_name, backend_start, xact_start
FROM pg_stat_activity 
WHERE application_name LIKE '%batch%' OR query LIKE '%reconcil%';

-- Find user-facing transactions holding locks
SELECT pid, query, application_name, xact_start, 
       now() - xact_start as tx_duration
FROM pg_stat_activity 
WHERE application_name LIKE '%order-service%'
  AND state = 'active'
ORDER BY tx_duration DESC;
```

**Step 3: Thread dump to see the locking pattern**
```bash
jcmd <pid> Thread.print > /tmp/td.txt

# Look for BLOCKED threads
grep -c "BLOCKED" /tmp/td.txt
# Result: 34 threads BLOCKED

# Look at what they're blocked on
grep -B 5 -A 20 "BLOCKED" /tmp/td.txt
```

**Step 4: Identify lock ordering difference**
```sql
-- Batch job acquires locks in this order:
-- UPDATE inventory SET quantity = ... WHERE product_id IN (1, 2, 3, 4, 5, ...)
-- (Locks rows in product_id order based on batch chunk)

-- User transaction acquires locks in this order:
-- 1. UPDATE orders SET status = 'CONFIRMED' WHERE id = 999    (locks order row)
-- 2. UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 3  (locks inventory)
-- 3. UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 1  (locks inventory)
-- (Locks inventory rows in ORDER ITEM sequence, not product_id order)
```

### Root Cause

The batch reconciliation job and user-facing order transactions lock rows in **different orders**:

```java
// BATCH JOB - locks inventory rows in chunk order (product_id 1-100, then 101-200, etc.)
@Component
public class InventoryReconciliationJob {
    
    @Scheduled(cron = "0 0 10 * * *")  // 10 AM - during peak traffic!
    @Transactional
    public void reconcile() {
        List<InventoryDiscrepancy> discrepancies = warehouseClient.getDiscrepancies();
        
        for (InventoryDiscrepancy d : discrepancies) {
            // Locks product_id=1, then product_id=2, then product_id=3...
            Inventory inv = inventoryRepo.findByProductIdForUpdate(d.getProductId());
            inv.setQuantity(d.getActualQuantity());
        }
        // Holds ALL locks until end of transaction (could be minutes)
    }
}

// USER TRANSACTION - locks inventory rows in order-item sequence
@Service
public class OrderService {
    
    @Transactional
    public void confirmOrder(Long orderId) {
        Order order = orderRepo.findById(orderId).orElseThrow();
        order.setStatus("CONFIRMED");
        
        // Order items might be: product_id=5, product_id=2, product_id=8
        for (OrderItem item : order.getItems()) {
            // Locks product_id=5, then product_id=2, then product_id=8
            Inventory inv = inventoryRepo.findByProductIdForUpdate(item.getProductId());
            inv.setQuantity(inv.getQuantity() - item.getQuantity());
        }
    }
}
```

**Deadlock scenario:**
- Batch: holds lock on product_id=2, waiting for product_id=5
- User tx: holds lock on product_id=5, waiting for product_id=2
- → DEADLOCK

### Immediate Fix

```bash
# Kill the batch job
# Find the PostgreSQL PID
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = 'batch-reconciliation';"

# Or cancel the specific query (less aggressive)
psql -c "SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE application_name = 'batch-reconciliation';"
```

### Permanent Fix

```java
// Fix 1: Consistent lock ordering - ALWAYS lock in product_id order
@Service
public class OrderService {
    
    @Transactional
    public void confirmOrder(Long orderId) {
        Order order = orderRepo.findById(orderId).orElseThrow();
        order.setStatus("CONFIRMED");
        
        // Sort items by product_id to ensure consistent lock ordering
        List<OrderItem> sortedItems = order.getItems().stream()
            .sorted(Comparator.comparing(OrderItem::getProductId))
            .toList();
        
        for (OrderItem item : sortedItems) {
            inventoryRepo.decrementQuantity(item.getProductId(), item.getQuantity());
        }
    }
}

// Fix 2: Batch job uses SKIP LOCKED to avoid contention
@Component
public class InventoryReconciliationJob {
    
    @Scheduled(cron = "0 0 3 * * *")  // Move to off-peak: 3 AM
    public void reconcile() {
        List<InventoryDiscrepancy> discrepancies = warehouseClient.getDiscrepancies();
        
        // Process in small batches with individual transactions
        Lists.partition(discrepancies, 10).forEach(batch -> {
            processSmallBatch(batch);
        });
    }
    
    @Transactional(timeout = 5)  // Short timeout - fail fast
    public void processSmallBatch(List<InventoryDiscrepancy> batch) {
        // Sort by product_id for consistent ordering
        batch.sort(Comparator.comparing(InventoryDiscrepancy::getProductId));
        
        for (InventoryDiscrepancy d : batch) {
            // Use SKIP LOCKED - if row is locked, skip it and retry later
            Optional<Inventory> inv = inventoryRepo.findByProductIdSkipLocked(d.getProductId());
            inv.ifPresent(i -> i.setQuantity(d.getActualQuantity()));
        }
    }
}

// Fix 3: Repository with SKIP LOCKED
public interface InventoryRepository extends JpaRepository<Inventory, Long> {
    
    @Query("SELECT i FROM Inventory i WHERE i.productId = :productId")
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @QueryHints(@QueryHint(name = "javax.persistence.lock.timeout", value = "0"))  // NOWAIT
    Optional<Inventory> findByProductIdForUpdate(@Param("productId") Long productId);
    
    @Query(value = "SELECT * FROM inventory WHERE product_id = :productId FOR UPDATE SKIP LOCKED",
           nativeQuery = true)
    Optional<Inventory> findByProductIdSkipLocked(@Param("productId") Long productId);
}
```

### Prevention

1. **Consistent lock ordering**: Document and enforce that all code locks rows in the same order (e.g., always by primary key ascending)
2. **Batch jobs run off-peak** and use small transaction batches
3. **Use `lock_timeout`** at session level: `SET lock_timeout = '3s'`
4. **SKIP LOCKED** for batch jobs that can retry
5. **Monitor `pg_stat_database.deadlocks`** — alert if > 0
6. **Separate batch and OLTP workloads** — use read replicas for reconciliation reads

---

## Incident 6: N+1 Explosion After "Small Refactoring"

### Alert/Symptoms

```
ALERT: p99 latency for GET /api/departments jumped from 50ms to 8 seconds
ALERT: Database connections active: 10/10 (saturated)
ALERT: PostgreSQL queries per second: jumped from 200 to 15,000

Timeline: Deployed PR #1847 "Refactor: use Spring Data derived queries" 2 hours ago
```

### Investigation Steps

**Step 1: Check Hibernate statistics**
```bash
# Enable stats temporarily via actuator (if configured)
curl -X POST http://localhost:8080/actuator/hibernate-statistics/enable

curl http://localhost:8080/actuator/metrics/hibernate.query.executions
# Before deploy: ~5 queries per request
# After deploy: ~500 queries per request
```

**Step 2: Enable SQL logging temporarily**
```bash
# Set log level dynamically via actuator
curl -X POST http://localhost:8080/actuator/loggers/org.hibernate.SQL \
  -H 'Content-Type: application/json' -d '{"configuredLevel":"DEBUG"}'

# Check logs - see N+1 pattern
kubectl logs -l app=dept-service --tail=100
```

```
-- The log shows:
Hibernate: select d.* from departments d                    -- 1 query
Hibernate: select e.* from employees e where e.dept_id=?   -- repeated 50x
Hibernate: select p.* from projects p where p.dept_id=?    -- repeated 50x  
Hibernate: select e.* from employees e where e.dept_id=?   -- 50x again (different caller?)
-- Total: 1 + 50 + 50 + 50 = 151 queries for one API call!
```

**Step 3: Identify the change via git**
```bash
git log --oneline -5
# abc1234 Refactor: use Spring Data derived queries instead of custom JPQL

git diff abc1234^..abc1234 -- src/
```

**Step 4: The diff reveals the problem**
```diff
-    @Query("SELECT d FROM Department d " +
-           "JOIN FETCH d.employees " +
-           "JOIN FETCH d.projects")
-    List<Department> findAllWithDetails();
+    List<Department> findAll();  // "simplified" - removed "unnecessary" custom query
```

### Root Cause

A developer replaced a custom `JOIN FETCH` query with a Spring Data derived `findAll()` method, thinking it was "cleaner." The original query fetched associations in a single SQL query. The new code:

```java
// BEFORE (efficient - 1 query)
@Query("SELECT d FROM Department d JOIN FETCH d.employees JOIN FETCH d.projects")
List<Department> findAllWithDetails();

// AFTER the "refactoring" (N+1 - 1 + N + N queries)
List<Department> findAll();  // No JOIN FETCH

// The service layer still accesses lazy collections:
@Service
public class DepartmentService {
    
    public List<DepartmentDTO> getAllDepartments() {
        List<Department> departments = departmentRepository.findAll();
        
        return departments.stream()
            .map(dept -> new DepartmentDTO(
                dept.getName(),
                dept.getEmployees().size(),    // LAZY LOAD - 1 query per department
                dept.getProjects().stream()    // LAZY LOAD - 1 query per department
                    .map(Project::getName)
                    .toList()
            ))
            .toList();
    }
}
```

### Immediate Fix

```bash
# Rollback the deployment
kubectl rollout undo deployment/dept-service

# Or revert the commit
git revert abc1234
git push
```

### Permanent Fix

```java
// Option 1: Restore the JOIN FETCH query
@Query("SELECT DISTINCT d FROM Department d " +
       "LEFT JOIN FETCH d.employees " +
       "LEFT JOIN FETCH d.projects")
List<Department> findAllWithDetails();

// Option 2: Use EntityGraph
@EntityGraph(attributePaths = {"employees", "projects"})
List<Department> findAll();

// Option 3: Projection query (best for DTOs - no entity overhead)
@Query("SELECT new com.myapp.dto.DepartmentDTO(" +
       "d.name, SIZE(d.employees), d.projects) " +
       "FROM Department d")
List<DepartmentDTO> findAllDepartmentSummaries();

// Option 4: Batch fetching (if you can't change the query)
@Entity
@BatchSize(size = 50)  // Fetches up to 50 collections in one query
public class Department {
    
    @OneToMany(mappedBy = "department")
    @BatchSize(size = 50)
    private List<Employee> employees;
}
```

### Prevention

1. **Integration tests that assert query count**:
```java
@Test
void findAllDepartments_shouldNotExceedQueryLimit() {
    // Given 50 departments with employees and projects
    
    Statistics stats = entityManagerFactory.unwrap(SessionFactory.class).getStatistics();
    stats.clear();
    
    departmentService.getAllDepartments();
    
    // Must not exceed 3 queries (1 for depts, 1 batch for employees, 1 batch for projects)
    assertThat(stats.getQueryExecutionCount()).isLessThanOrEqualTo(3);
}
```

2. **PR review checklist**: Any removal of `@Query` or `JOIN FETCH` must include query count test
3. **Hibernate query count assertion in CI**: Fail build if query count regresses
4. **Use `spring.jpa.properties.hibernate.generate_statistics=true` in test profile**
5. **Log slow query count per request** via interceptor — alert if > 20 queries per request

---

## Incident 7: L2 Cache Serving Stale/Wrong Tenant Data

### Alert/Symptoms

```
ALERT: Customer support escalation - "seeing another company's data"
ALERT: Security team notified - potential data breach

Reports:
- Tenant A users see Tenant B's configuration/pricing
- Intermittent - not every request
- Only affects "Settings" and "Pricing" pages
- Started after enabling Hibernate L2 cache last week
```

### Investigation Steps

**Step 1: Reproduce and identify cache involvement**
```bash
# Check if disabling cache fixes it
curl -X POST http://localhost:8080/actuator/caches/evict-all

# After cache eviction, problem disappears temporarily
# Returns after cache warms up again - confirms cache issue
```

**Step 2: Check cache configuration**
```bash
grep -r "cache\|@Cacheable\|@Cache" src/ --include="*.java"
grep -r "cache" src/main/resources/ --include="*.yml" --include="*.properties"
```

**Step 3: Examine cached entity and its key**
```java
// Found the problematic entity
@Entity
@Table(name = "tenant_settings")
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class TenantSettings {
    @Id
    @GeneratedValue
    private Long id;
    
    private String tenantId;    // Tenant discriminator
    private String settingKey;
    private String settingValue;
}
```

**Step 4: Check how the entity is queried**
```java
// The problematic query - result is cached by query cache
@Cacheable("tenantSettings")  // Spring Cache - key defaults to method params!
public TenantSettings getSettings(String settingKey) {
    // BUG: tenantId comes from SecurityContext, NOT from method param
    String tenantId = SecurityContextHolder.getContext().getTenantId();
    return settingsRepo.findByTenantIdAndSettingKey(tenantId, settingKey);
}
```

**Step 5: Verify the cache key issue**
```bash
# Connect to Redis/Ehcache and inspect keys
redis-cli KEYS "tenantSettings*"
# Shows: tenantSettings::pricing_tier
# Shows: tenantSettings::max_users
# NO tenant discriminator in the key!
```

### Root Cause

The Spring `@Cacheable` annotation defaults to using method parameters as the cache key. The `getSettings("pricing_tier")` method only takes `settingKey` as a parameter — the `tenantId` comes from `SecurityContext` and is NOT part of the cache key.

```java
// What happens:
// 1. Tenant A calls getSettings("pricing_tier") → cache miss → queries DB → caches result with key "pricing_tier"
// 2. Tenant B calls getSettings("pricing_tier") → cache HIT → returns Tenant A's data!
```

For Hibernate L2 cache specifically, the issue could also be:
```java
// Entity cache uses entity ID as key - safe for entities
// BUT Query cache uses query + parameters as key
// If a filter-based multi-tenancy (@FilterDef) isn't applied consistently,
// the query cache returns results from wrong tenant

@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = "string"))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class TenantSettings { ... }

// If the filter is not enabled before a cached query, wrong tenant data is returned
```

### Immediate Fix

```bash
# IMMEDIATELY disable cache - this is a data breach
curl -X POST http://localhost:8080/actuator/caches/evict-all

# Deploy config change to disable caching
kubectl set env deployment/app-service SPRING_CACHE_TYPE=none

# Notify security team - log all affected requests for breach report
```

### Permanent Fix

```java
// Fix 1: Include tenantId in cache key
@Cacheable(value = "tenantSettings", 
           key = "T(com.myapp.security.TenantContext).getCurrentTenantId() + ':' + #settingKey")
public TenantSettings getSettings(String settingKey) {
    String tenantId = TenantContext.getCurrentTenantId();
    return settingsRepo.findByTenantIdAndSettingKey(tenantId, settingKey);
}

// Fix 2: Custom key generator that always includes tenant
@Component
public class TenantAwareCacheKeyGenerator implements KeyGenerator {
    
    @Override
    public Object generate(Object target, Method method, Object... params) {
        String tenantId = TenantContext.getCurrentTenantId();
        return tenantId + ":" + StringUtils.arrayToDelimitedString(params, ":");
    }
}

// Apply globally
@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public KeyGenerator keyGenerator() {
        return new TenantAwareCacheKeyGenerator();
    }
}

// Fix 3: For Hibernate L2 cache - use cache region per tenant
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "tenant_settings")
public class TenantSettings {
    // Use composite cache key including tenant
    @org.hibernate.annotations.CacheRegion("tenant_settings")
}

// Fix 4: Disable query cache for multi-tenant queries
// application.yml:
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_query_cache: false  # Dangerous in multi-tenant apps
          use_second_level_cache: true  # Entity cache by ID is safe

// Fix 5: Separate cache instances per tenant (Redis)
@Configuration
public class CacheConfig {
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory factory) {
        return new TenantAwareCacheManager(factory);  // Prefixes all keys with tenantId
    }
}
```

### Prevention

1. **NEVER use query cache in multi-tenant applications** unless keys explicitly include tenant
2. **Mandatory code review rule**: All `@Cacheable` annotations must include tenant in key
3. **Integration test**: Verify tenant isolation with cache enabled
```java
@Test
void cacheMustNotLeakBetweenTenants() {
    setTenant("tenant-a");
    TenantSettings settingsA = service.getSettings("pricing");
    
    setTenant("tenant-b");
    TenantSettings settingsB = service.getSettings("pricing");
    
    assertThat(settingsA.getTenantId()).isEqualTo("tenant-a");
    assertThat(settingsB.getTenantId()).isEqualTo("tenant-b");
    assertThat(settingsA).isNotEqualTo(settingsB);
}
```
4. **Use a custom CacheManager that enforces tenant prefixing** — make it impossible to forget
5. **Security audit**: Periodically test cross-tenant data access

---

## Incident 8: Optimistic Lock Exception Storm

### Alert/Symptoms

```
ALERT: org.hibernate.StaleObjectStateException rate > 200/min (baseline: 2/min)
ALERT: HTTP 500 error rate spike to 15%
ALERT: Customer complaints: "Save failed, please try again" — but retrying doesn't help

Application logs flooding with:
ERROR: Row was updated or deleted by another transaction (or unsaved-value mapping was incorrect)
org.hibernate.StaleObjectStateException: Row was updated or deleted by another transaction
  : [com.myapp.entity.Product#12345]
```

### Investigation Steps

**Step 1: Identify which entity and what's updating it**
```bash
# Count exceptions by entity
kubectl logs -l app=product-service --since=1h | grep "StaleObjectState" | 
  sed 's/.*\[//;s/#.*//' | sort | uniq -c | sort -rn

# Output:
# 4521 com.myapp.entity.Product
# 234  com.myapp.entity.Category
# 12   com.myapp.entity.Inventory
```

**Step 2: Check what's updating Product so frequently**
```sql
-- Track version column changes
SELECT id, version, updated_at, updated_by
FROM products 
WHERE updated_at > now() - interval '10 minutes'
ORDER BY updated_at DESC LIMIT 50;

-- Check version increment rate
SELECT id, version FROM products WHERE id = 12345;
-- version: 4,721 (was 100 yesterday - something is hammering this entity)
```

**Step 3: Identify the batch job**
```bash
kubectl logs -l app=product-service --since=1h | grep "batch\|scheduled\|cron"
# Found: "Executing price-update batch job - 50000 products"
```

**Step 4: Check the cascade issue**
```java
// Found in Product entity:
@ManyToOne(cascade = CascadeType.ALL)
@JoinColumn(name = "category_id")
private Category category;  // Shared entity!

// The batch job updates Product, which CASCADEs to Category
// Every product update increments Category's version
// All concurrent user edits to products in same category FAIL
```

### Root Cause

Two compounding issues:

**Issue A: Batch job updating shared parent entity via cascade**
```java
@Entity
public class Product {
    @Id
    private Long id;
    
    @Version
    private Long version;
    
    private BigDecimal price;
    
    @ManyToOne(cascade = CascadeType.ALL)  // PROBLEM: cascade ALL on shared entity
    private Category category;
}

// Batch job:
@Scheduled(fixedRate = 300000)  // Every 5 minutes
@Transactional
public void updatePrices() {
    List<Product> products = productRepo.findByPriceUpdatePending(true);
    for (Product p : products) {
        p.setPrice(pricingEngine.calculate(p));
        // Because of CascadeType.ALL, Hibernate dirty-checks Category too
        // If Category is "dirty" (e.g., lastModified touched), it increments Category.version
        // All other transactions working on products in same category get OptimisticLockException
    }
}
```

**Issue B: No retry logic — users see raw 500 error**
```java
@PutMapping("/products/{id}")
@Transactional
public ProductResponse updateProduct(@PathVariable Long id, @RequestBody ProductRequest req) {
    Product product = productRepo.findById(id).orElseThrow();
    product.setName(req.getName());
    product.setDescription(req.getDescription());
    productRepo.save(product);
    return ProductResponse.from(product);
    // If OptimisticLockException occurs, it bubbles up as HTTP 500
}
```

### Immediate Fix

```bash
# Stop the batch job
kubectl set env deployment/product-service PRICE_UPDATE_ENABLED=false
kubectl rollout restart deployment/product-service

# Alternatively, kill specific scheduled task via actuator (if exposed)
```

### Permanent Fix

```java
// Fix 1: Remove cascade from shared entities
@Entity
public class Product {
    @Id
    private Long id;
    
    @Version
    private Long version;
    
    private BigDecimal price;
    
    @ManyToOne  // NO CASCADE - Category is managed independently
    @JoinColumn(name = "category_id")
    private Category category;
}

// Fix 2: Add retry logic for optimistic lock failures
@Service
public class ProductService {
    
    @Retryable(
        retryFor = OptimisticLockingFailureException.class,
        maxAttempts = 3,
        backoff = @Backoff(delay = 100, multiplier = 2)
    )
    @Transactional
    public ProductResponse updateProduct(Long id, ProductRequest req) {
        Product product = productRepo.findById(id).orElseThrow();
        product.setName(req.getName());
        product.setDescription(req.getDescription());
        return ProductResponse.from(productRepo.save(product));
    }
    
    @Recover
    public ProductResponse recoverFromOptimisticLock(
            OptimisticLockingFailureException ex, Long id, ProductRequest req) {
        throw new ConflictException("Product was modified by another user. Please refresh and retry.");
    }
}

// Fix 3: Batch job uses direct UPDATE without loading entity graph
@Modifying
@Query("UPDATE Product p SET p.price = :price WHERE p.id = :id")
void updatePrice(@Param("id") Long id, @Param("price") BigDecimal price);
// This doesn't trigger cascades or version conflicts on related entities

// Fix 4: If batch must load entities, use explicit version check
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void updateSingleProductPrice(Long productId) {
    try {
        Product p = productRepo.findById(productId).orElseThrow();
        p.setPrice(pricingEngine.calculate(p));
        productRepo.saveAndFlush(p);
    } catch (OptimisticLockingFailureException e) {
        log.warn("Skipping product {} - concurrent modification, will retry next cycle", productId);
    }
}

// Fix 5: Enable Spring Retry
@Configuration
@EnableRetry
public class RetryConfig {
}
```

### Prevention

1. **Never use `CascadeType.ALL` on `@ManyToOne`** — shared parent entities must be managed independently
2. **All `@Version`-annotated entities must have retry logic** at the service layer
3. **Batch jobs should use `@Modifying` queries** for bulk updates to avoid loading entity graphs
4. **Return HTTP 409 (Conflict)** instead of 500 for optimistic lock failures
5. **Monitor `StaleObjectStateException` rate** — alert if > 10/min
6. **Separate batch operations from OLTP** — use different time windows or CQRS

---

## Thread Dump Reading Cheat Sheet

### Pattern: "Waiting for Connection" (Pool Exhaustion)
```
"http-nio-8080-exec-42" TIMED_WAITING
    at java.lang.Object.wait(Native Method)
    at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:228)
    at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:162)
    at org.hibernate.engine.jdbc.connections.internal.DatasourceConnectionProviderImpl.getConnection(...)
```
→ Thread is waiting for a free connection from the pool

### Pattern: "BLOCKED on Monitor Lock" (Thread Contention)
```
"http-nio-8080-exec-12" BLOCKED
    at com.myapp.service.SomeService.syncMethod(SomeService.java:45)
    - waiting to lock <0x00000007b88d0a08> (a com.myapp.service.SomeService)
    - locked by "http-nio-8080-exec-7"
```
→ Synchronized method creating a bottleneck

### Pattern: "Stuck in I/O" (External Service Slow/Down)
```
"http-nio-8080-exec-33" RUNNABLE
    at java.net.SocketInputStream.socketRead0(Native Method)
    at java.net.SocketInputStream.read(SocketInputStream.java:152)
    at okhttp3.internal.http1.Http1ExchangeCodec$FixedLengthSource.read(...)
    at com.myapp.client.PaymentClient.charge(PaymentClient.java:67)
```
→ Thread stuck waiting for external HTTP response

### Pattern: "Database Lock Wait"
```
"http-nio-8080-exec-5" RUNNABLE
    at org.postgresql.core.VisibleBufferedInputStream.readMore(...)
    at org.postgresql.core.PGStream.receiveChar(PGStream.java:...)
    at org.postgresql.core.QueryExecutorImpl.processResults(...)
    at com.myapp.repository.OrderRepository.save(OrderRepository.java:...)
```
→ Thread waiting for database lock to be released (appears RUNNABLE because it's doing I/O)

### Quick Diagnostic Commands

```bash
# Count threads by state
jcmd <pid> Thread.print | grep "java.lang.Thread.State" | sort | uniq -c

# Count threads waiting for HikariCP connection
jcmd <pid> Thread.print | grep -c "HikariPool.getConnection"

# Count threads blocked on locks
jcmd <pid> Thread.print | grep -c "BLOCKED"

# Find what's holding locks
jcmd <pid> Thread.print | grep -B 1 "locked <"

# Find deadlocks
jcmd <pid> Thread.print | grep -A 50 "Found.*deadlock"
```

---

## Summary: Incident Response Playbook

| Symptom | First Check | Tool |
|---------|-------------|------|
| Connection pool exhaustion | Thread dump + HikariCP JMX | `jcmd Thread.print` |
| Gradual memory growth | Heap dump + dominator tree | MAT / `jcmd GC.heap_dump` |
| Sudden query slowness | `pg_stat_statements` + `EXPLAIN ANALYZE` | psql |
| Duplicate records | Idempotency key check + timing analysis | SQL grouping |
| Deadlocks | `pg_locks` + lock ordering analysis | PostgreSQL logs |
| N+1 explosion | Hibernate statistics + SQL log count | Actuator/logs |
| Wrong data from cache | Cache key inspection + tenant check | Redis CLI / logs |
| Optimistic lock storms | Version column history + cascade check | SQL + entity mapping |

### Golden Rules

1. **Take 3 thread dumps 10 seconds apart** — one dump is a snapshot, three show a pattern
2. **Always check what changed** — deployment, config, data volume, traffic pattern
3. **Correlate timestamps** — when did the alert fire vs. when did something change
4. **Don't restart until you have diagnostic data** — heap dump, thread dump, metrics
5. **Fix the immediate pain first, then fix the root cause** — stop the bleeding, then surgery
