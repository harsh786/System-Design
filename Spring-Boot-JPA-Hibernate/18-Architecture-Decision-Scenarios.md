# Architecture Decision Scenarios (Staff Engineer / Architect Level)

> These are open-ended design questions that test your ability to analyze trade-offs, justify decisions under constraints, and communicate technical reasoning clearly. This is the format most commonly used in Staff+ interview loops.

---

## Scenario 1: Choosing Between JPA and Alternatives

### Problem Statement

Your team is building a new **payment processing service**. Requirements:
- 5,000 TPS sustained, 15,000 TPS peak
- Strict latency: p99 < 50ms for payment status queries, p99 < 200ms for payment initiation
- Complex audit trail: every state change must be recorded with who/what/when/why
- Legacy Oracle database with 200+ tables (shared with other services during migration)
- Team of 8 developers: 6 experienced with Spring/JPA, 2 with raw JDBC/jOOQ
- Compliance: PCI DSS requirements

### Constraints
- Must integrate with existing Oracle schema (can't redesign)
- Need to support both read-heavy (status queries) and write-heavy (payment processing) paths
- Audit trail must be tamper-proof and complete
- Must be production-ready in 4 months

### Option Analysis

| Criterion | Spring Data JPA | Spring Data JDBC | jOOQ | Raw JDBC |
|-----------|----------------|-----------------|------|----------|
| Team familiarity | High (6/8) | Low | Low (2/8) | Medium |
| Latency overhead | Medium (~5-10ms) | Low (~2-3ms) | Low (~2-3ms) | Lowest (~1ms) |
| Legacy schema compat | Good (flexible mapping) | Limited (simple tables) | Excellent (generates from schema) | Excellent |
| Audit trail support | Hibernate Envers built-in | Manual | Manual | Manual |
| Boilerplate code | Low | Medium | Medium | High |
| Batch performance | Good (with tuning) | Good | Excellent | Excellent |
| Debugging complexity | High (proxy magic) | Low (transparent) | Medium | Low |
| N+1 risk | High | None (no lazy loading) | None | None |
| Connection holding | OSIV risk | Short | Short | Shortest |
| Testability | Medium (needs real DB) | Good | Good | Medium |
| Time to production | Fast (familiar) | Medium | Medium | Slow |

### Recommended Approach: Hybrid

```
Payment Processing Service
├── WRITE PATH (Payment Initiation): jOOQ or Spring Data JDBC
│   ├── Simple, predictable SQL
│   ├── Tight latency control
│   ├── Batch operations for settlement
│   └── Direct control over transactions
│
├── READ PATH (Status Queries): Spring Data JPA with projections
│   ├── Team familiarity speeds development
│   ├── DTO projections for performance
│   ├── L2 cache for hot data
│   └── @Transactional(readOnly=true) on replica
│
├── AUDIT TRAIL: Hibernate Envers OR CDC-based
│   ├── Envers: automatic, JPA-integrated
│   └── CDC: more flexible, decoupled
│
└── LEGACY INTEGRATION: jOOQ for complex Oracle queries
    ├── Code generation from Oracle schema
    ├── Oracle-specific syntax support
    └── No object-relational impedance mismatch
```

### Justification
1. **Team velocity** matters: 6/8 developers productive with JPA on day one
2. **Latency-critical path** (write) uses lighter framework, doesn't fight JPA overhead
3. **jOOQ for legacy**: type-safe queries generated from Oracle catalog, handles Oracle quirks
4. **Envers for audit**: free with JPA, meets compliance without custom code
5. **4-month deadline**: hybrid lets the team start fast on familiar ground while optimizing critical paths

### Follow-up Questions
- "How would you handle the transition if you later need to ditch JPA entirely?"
- "How do you ensure consistency between JPA read path and jOOQ write path?"
- "What's your caching strategy for the read path?"
- "How do you test Oracle-specific queries in CI?"

### Red Flags (Answers that fail the interview)
- Choosing one technology dogmatically without analyzing trade-offs
- "JPA for everything because the team knows it" (ignoring latency constraints)
- "Raw JDBC for max performance" (ignoring 4-month deadline and team expertise)
- Not considering the audit trail requirements upfront
- Ignoring connection management differences between technologies

---

## Scenario 2: Multi-Tenancy Architecture Decision

### Problem Statement

You're building a **B2B SaaS platform** for project management. Requirements:
- Launch with 50 tenants, scale to 5,000 within 2 years
- Tenant sizes: range from 100 users (SMB) to 50,000 users (enterprise)
- 5 enterprise tenants require HIPAA compliance (data isolation guarantee)
- Budget: startup, limited infrastructure budget initially
- Feature: tenants can customize workflows (different schema extensions)

### Constraints
- Must demonstrate data isolation to enterprise customers during sales process
- Cannot afford dedicated infrastructure per tenant at SMB tier
- Need to support per-tenant backup/restore for enterprise
- Schema migrations must not require downtime across all tenants
- Cost per tenant must decrease as you scale

### Option Analysis

```
┌────────────────────┬───────────────────┬──────────────────┬────────────────────┬────────────────┐
│ Criterion          │ Shared DB +       │ Schema per       │ Database per       │ Hybrid         │
│                    │ Discriminator     │ Tenant           │ Tenant             │                │
├────────────────────┼───────────────────┼──────────────────┼────────────────────┼────────────────┤
│ Data isolation     │ Low (row-level)   │ High (schema)    │ Highest (full DB)  │ Tiered         │
│ Cost at 50 tenants │ Lowest            │ Low              │ Medium             │ Low            │
│ Cost at 5000       │ Lowest            │ High (5K schemas)│ Very High (5K DBs) │ Medium         │
│ Connection pool    │ Single pool       │ Pool per schema  │ Pool per DB        │ Tiered         │
│ Migration ease     │ 1 migration       │ 5000 migrations! │ 5000 migrations!   │ 1 + N (small)  │
│ Query complexity   │ WHERE tenant_id=? │ SET search_path  │ Route datasource   │ Depends on tier│
│ Backup/restore     │ Complex (extract) │ Medium (pg_dump) │ Easy (full backup) │ Tiered         │
│ Compliance demo    │ Hard to prove     │ Easy to prove    │ Trivial to prove   │ Easy           │
│ Schema extension   │ JSON columns      │ Custom per schema│ Full flexibility   │ Tiered         │
│ Cross-tenant query │ Easy              │ Complex          │ Very Complex       │ Depends        │
│ Operational load   │ Minimal           │ Medium           │ Very High          │ Medium         │
│ Noisy neighbor     │ High risk         │ Medium risk      │ No risk            │ Tiered         │
└────────────────────┴───────────────────┴──────────────────┴────────────────────┴────────────────┘
```

### Recommended Approach: Tiered Hybrid

```
┌─────────────────────────────────────────────────────────────────┐
│ TIER 1: SMB Tenants (100-500 users) - Shared Database           │
│ ├── Discriminator column (tenant_id) on all tables              │
│ ├── Shared connection pool                                       │
│ ├── Row-level security (PostgreSQL RLS policies)                │
│ ├── Hibernate @Filter for tenant isolation                      │
│ └── Cost: pennies per tenant                                    │
│                                                                   │
│ TIER 2: Mid-Market (500-10K users) - Schema per Tenant          │
│ ├── Separate PostgreSQL schema per tenant                        │
│ ├── Shared database, separate schemas                           │
│ ├── Connection pool shared but schema switched per request      │
│ ├── Can demonstrate isolation (separate tables)                 │
│ └── Cost: moderate (shared infra, separate logical space)       │
│                                                                   │
│ TIER 3: Enterprise (10K+ users, HIPAA) - Database per Tenant    │
│ ├── Dedicated database instance (or RDS instance)               │
│ ├── Dedicated connection pool                                    │
│ ├── Independent backup/restore                                   │
│ ├── Custom schema extensions possible                           │
│ ├── Can provide compliance certificates per DB                  │
│ └── Cost: high (dedicated resources, premium pricing)           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### JPA Implementation

```java
// Tenant context (set by filter/interceptor)
public class TenantContext {
    private static final ThreadLocal<String> currentTenant = new ThreadLocal<>();
    private static final ThreadLocal<TenantTier> currentTier = new ThreadLocal<>();
    
    public static void setTenant(String tenantId, TenantTier tier) {
        currentTenant.set(tenantId);
        currentTier.set(tier);
    }
}

// Tier 1: Discriminator approach with @Filter
@Entity
@Table(name = "projects")
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Project {
    @Id @GeneratedValue private Long id;
    @Column(nullable = false) private String tenantId;
    private String name;
}

// Tier 2 & 3: Routing datasource
public class TenantRoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        TenantTier tier = TenantContext.getCurrentTier();
        if (tier == TenantTier.ENTERPRISE) {
            return "db-" + TenantContext.getCurrentTenant();
        } else if (tier == TenantTier.MID_MARKET) {
            return "shared-db"; // Schema switched via Hibernate setting
        } else {
            return "shared-db"; // Discriminator-based
        }
    }
}

// Hibernate multi-tenancy config for schema strategy
@Configuration
public class HibernateMultiTenantConfig {
    @Bean
    public MultiTenantConnectionProvider connectionProvider(DataSource dataSource) {
        return new SchemaMultiTenantConnectionProvider(dataSource);
    }
    
    @Bean
    public CurrentTenantIdentifierResolver tenantResolver() {
        return () -> TenantContext.getCurrentTenant();
    }
}
```

### Tenant Upgrade Path
```
SMB signs up → Tier 1 (shared, discriminator)
    │
    │ Grows to 1000 users, wants isolation
    ▼
Upgrade to Tier 2 (schema):
    1. Create new schema
    2. Migrate data: INSERT INTO new_schema.projects SELECT * FROM projects WHERE tenant_id = 'X'
    3. Update tenant config to schema strategy
    4. Delete rows from shared tables
    │
    │ Becomes enterprise, needs HIPAA
    ▼
Upgrade to Tier 3 (database):
    1. Provision new database
    2. pg_dump schema → pg_restore to new DB
    3. Update tenant config to dedicated datasource
    4. Drop schema from shared DB
```

### Follow-up Questions
- "How do you handle migrations across 5000 schemas?"
- "What's your connection pool strategy at 5000 tenants?"
- "How do you do cross-tenant analytics/reporting?"
- "How do you handle a Tier 1 tenant that becomes a noisy neighbor?"
- "What's the backup strategy for each tier?"

---

## Scenario 3: Event-Driven Decomposition

### Problem Statement

Current state: a monolithic `placeOrder()` method:

```java
@Transactional
public OrderResponse placeOrder(OrderRequest request) {
    // 1. Validate inventory (DB query)
    // 2. Create order record (DB insert)
    // 3. Charge payment via Stripe API (HTTP call, 500ms-2s)
    // 4. Reserve inventory (DB update)
    // 5. Send confirmation email via SendGrid (HTTP call, 200ms-1s)
    // 6. Update analytics counters (DB update)
    // 7. Notify warehouse via webhook (HTTP call, 100ms-500ms)
    // 8. Update loyalty points (DB update)
    return new OrderResponse(order.getId(), "CONFIRMED");
}
// Total time: 2-5 seconds, holding DB connection entire time
// If Stripe fails at step 3: everything rolls back (including inventory check that was fine)
// If SendGrid is slow: customer waits 5 seconds for "order confirmed"
```

### Constraints
- Customer must see "Order Confirmed" within 1 second
- Payment MUST be charged before confirming order to customer
- Inventory MUST be reserved before confirming
- Email, analytics, warehouse notification can be delayed (seconds/minutes OK)
- System must be self-healing (if email fails, retry without losing order)
- Exactly-once semantics for payment (no double-charge)

### Recommended Design

```
┌─────────────────────────────────────────────────────────────────┐
│ SYNCHRONOUS (within customer's request, < 1 second)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  @Transactional (JPA Transaction)                                │
│  ├── 1. Reserve inventory (DB: UPDATE stock SET reserved += qty) │
│  ├── 2. Create order (DB: INSERT order with status=PENDING)      │
│  ├── 3. Charge payment (Stripe API: pre-authorized/captured)    │
│  │       ├── Success: Update order status = CONFIRMED           │
│  │       └── Failure: Release inventory, throw PaymentException │
│  ├── 4. Write outbox event: OrderConfirmedEvent                  │
│  └── COMMIT (order + inventory + outbox in single TX)           │
│                                                                   │
│  Return to customer: "Order Confirmed" (< 1 second)             │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│ ASYNCHRONOUS (via Outbox → Kafka, eventual)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  OrderConfirmedEvent consumed by:                                │
│  ├── Email Service → sends confirmation email (retry on failure) │
│  ├── Analytics Service → updates counters (idempotent)          │
│  ├── Warehouse Service → triggers pick/pack (retry on failure)  │
│  └── Loyalty Service → credits points (idempotent)              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Design Decisions

```java
@Service
public class OrderService {
    
    @Transactional
    public OrderResponse placeOrder(OrderRequest request) {
        // STEP 1: Reserve inventory (in our DB, fast)
        boolean reserved = inventoryService.reserve(
            request.getItems(), request.getIdempotencyKey());
        if (!reserved) throw new InsufficientInventoryException();
        
        // STEP 2: Create order (in our DB, fast)
        Order order = Order.create(request.getCustomerId(), request.getItems());
        order.setStatus(OrderStatus.PAYMENT_PENDING);
        orderRepository.save(order);
        
        // STEP 3: Charge payment (external API - this is the risk point)
        try {
            PaymentResult payment = paymentGateway.charge(
                request.getPaymentMethod(),
                order.getTotal(),
                order.getId()  // Idempotency key for Stripe
            );
            order.confirmPayment(payment.getTransactionId());
        } catch (PaymentException e) {
            // Payment failed → release inventory within SAME transaction
            inventoryService.release(request.getItems());
            order.setStatus(OrderStatus.PAYMENT_FAILED);
            throw new OrderPaymentFailedException(e);
        }
        
        // STEP 4: Write outbox event (same transaction as order)
        outboxService.publishEvent(
            "Order", order.getId().toString(), "OrderConfirmed",
            new OrderConfirmedEvent(order.getId(), order.getCustomerId(), 
                                    order.getTotal(), order.getItems())
        );
        
        return new OrderResponse(order.getId(), OrderStatus.CONFIRMED);
        // COMMIT: order + inventory + outbox all in one atomic TX
    }
}
```

### Key trade-off: Payment API inside transaction

```
Q: "Shouldn't you avoid HTTP calls inside @Transactional?"
A: Yes, generally. But here's the trade-off analysis:

Option A: Payment INSIDE transaction
├── Pro: Single atomic operation (order + payment + inventory)
├── Pro: Simple rollback on payment failure
├── Con: DB connection held during Stripe call (200ms-2s)
├── Con: Connection pool pressure under high load
└── Mitigation: Set strict timeout on payment call (2s max)
    Mitigation: Larger connection pool sized for peak
    Mitigation: Circuit breaker on payment gateway

Option B: Payment OUTSIDE transaction (Saga pattern)
├── Pro: DB connection released immediately
├── Pro: Better connection pool utilization
├── Con: More complex (need saga state machine)
├── Con: Customer might see "pending" status briefly
├── Con: Compensating transactions needed
└── When to choose: if payment takes > 5s consistently,
    or if you have extreme TPS requirements (>10K TPS)

Decision: Option A for systems < 5K TPS (simpler, adequate with timeout)
         Option B for systems > 5K TPS or unreliable payment gateway
```

### Follow-up Questions
- "What if Stripe times out? Did we charge or not?"
- "How do you handle the payment call throwing timeout but actually succeeding?"
- "What if the application crashes between payment success and DB commit?"
- "How would you change this design at 50K TPS?"

---

## Scenario 4: Caching Strategy for Read-Heavy System

### Problem Statement

**Product catalog service**: 
- 500K products, 50K categories
- Read:Write ratio: 1000:1
- Current p95 latency: 800ms (target: 100ms)
- Database is the bottleneck (slow JOINs for product + category + pricing + reviews)
- Products change ~100 times/day (price updates, stock changes)
- Categories change ~once/week
- Seasonal traffic: 10x spike during sales events

### Multi-Layer Cache Design

```
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 1: CDN / Edge Cache (Cloudflare/CloudFront)                │
│ ├── Cache product detail pages (HTML)                            │
│ ├── TTL: 60 seconds for product pages                           │
│ ├── TTL: 24 hours for category pages                            │
│ ├── Surrogate keys for targeted invalidation                    │
│ └── Handles 80% of traffic without hitting application           │
├──────────────────────────────────────────────────────────────────┤
│ LAYER 2: Application Cache (Redis)                               │
│ ├── Product DTO (fully assembled, ready to serve)               │
│ ├── TTL: 5 minutes for products                                 │
│ ├── TTL: 1 hour for categories                                  │
│ ├── Cache aside pattern with Spring @Cacheable                  │
│ ├── Handles remaining 80% of application-level requests         │
│ └── Invalidated on product update via event                     │
├──────────────────────────────────────────────────────────────────┤
│ LAYER 3: Hibernate L2 Cache (EhCache on-heap)                    │
│ ├── Product entity cache (for write operations needing entity)  │
│ ├── Category entity cache (rarely changes)                      │
│ ├── Query cache for category listings                           │
│ ├── Small: 10K most recently accessed products                  │
│ └── Handles cases where Redis is missed or for write paths      │
├──────────────────────────────────────────────────────────────────┤
│ LAYER 4: Database (PostgreSQL with read replica)                 │
│ ├── Primary: writes only                                        │
│ ├── Replica: complex queries, reports                           │
│ ├── Optimized indexes for remaining queries                     │
│ └── Only 0.1% of total read traffic reaches here               │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```java
@Service
public class ProductService {
    
    @Autowired private ProductRepository productRepository;
    @Autowired private RedisTemplate<String, ProductDTO> redisTemplate;
    @Autowired private ApplicationEventPublisher eventPublisher;
    
    // READ: Cache-aside with Redis
    public ProductDTO getProduct(Long productId) {
        String cacheKey = "product:" + productId;
        
        // L2: Check Redis
        ProductDTO cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) return cached;
        
        // L3/L4: Load from DB (Hibernate L2 cache may help here)
        Product product = productRepository.findWithDetailsById(productId)
            .orElseThrow(() -> new ProductNotFoundException(productId));
        
        ProductDTO dto = ProductDTO.from(product);
        
        // Populate Redis with TTL
        redisTemplate.opsForValue().set(cacheKey, dto, Duration.ofMinutes(5));
        
        return dto;
    }
    
    // WRITE: Update + Invalidate
    @Transactional
    public ProductDTO updateProduct(Long productId, ProductUpdateRequest request) {
        Product product = productRepository.findById(productId)
            .orElseThrow(() -> new ProductNotFoundException(productId));
        
        product.updateFrom(request);
        productRepository.save(product);
        
        // Invalidate caches
        String cacheKey = "product:" + productId;
        redisTemplate.delete(cacheKey);
        
        // Publish event for other cache layers (CDN, other instances)
        eventPublisher.publishEvent(new ProductUpdatedEvent(productId));
        
        return ProductDTO.from(product);
    }
}

// Cache stampede prevention
@Component
public class ProductCacheLoader {
    
    private final LoadingCache<Long, ProductDTO> localBuffer = Caffeine.newBuilder()
        .maximumSize(1000)
        .expireAfterWrite(Duration.ofSeconds(10))
        .refreshAfterWrite(Duration.ofSeconds(5))
        .build(this::loadProduct);
    
    // Probabilistic early expiration to prevent stampede
    public ProductDTO getWithAntiStampede(Long productId) {
        String cacheKey = "product:" + productId;
        ProductDTO cached = redisTemplate.opsForValue().get(cacheKey);
        
        if (cached != null) {
            // Probabilistic early refresh: 10% chance of refresh in last 20% of TTL
            if (shouldRefreshEarly(cached)) {
                CompletableFuture.runAsync(() -> refreshCache(productId));
            }
            return cached;
        }
        
        // Distributed lock to prevent multiple loaders
        String lockKey = "lock:product:" + productId;
        Boolean acquired = redisTemplate.opsForValue()
            .setIfAbsent(lockKey, "locked", Duration.ofSeconds(5));
        
        if (Boolean.TRUE.equals(acquired)) {
            try {
                ProductDTO dto = loadFromDB(productId);
                redisTemplate.opsForValue().set(cacheKey, dto, Duration.ofMinutes(5));
                return dto;
            } finally {
                redisTemplate.delete(lockKey);
            }
        } else {
            // Another thread is loading, wait briefly then retry
            Thread.sleep(50);
            return getWithAntiStampede(productId);
        }
    }
}
```

### Cache Invalidation Strategy

```
Product Update Flow:
1. Update in PostgreSQL (primary)
2. Invalidate Hibernate L2 cache (automatic via @Cache)
3. Delete Redis key (application code)
4. Publish CDN purge event (async, via outbox)
5. Other app instances receive event → invalidate local Caffeine cache

Eventual consistency window:
- Same instance: 0ms (immediate invalidation)
- Other instances: ~100ms (event propagation)
- Redis: 0ms (immediate delete)
- CDN: 1-5 seconds (purge propagation)
- Client browser: up to 60 seconds (if client cached)
```

### Follow-up Questions
- "What happens during a flash sale when cache hit ratio drops to 0%?"
- "How do you warm the cache before a planned sale event?"
- "What if Redis goes down? Graceful degradation strategy?"
- "How do you measure cache effectiveness?"
- "What's the memory budget for each cache layer?"

---

## Scenario 5: Database Scaling for 500M Row Table

### Problem Statement

Your `orders` table has grown to **500M rows**. Access patterns:
1. **Customer order history** (by customer_id, last 30 days): must be < 50ms
2. **Full-text search** across order descriptions: must be < 200ms
3. **Analytics dashboard** (aggregations by day/week/month): can be < 5s
4. **Real-time order status** updates: must be < 100ms write
5. **Compliance**: 7-year retention, must be queryable for audits

### Recommended Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ DATA ARCHITECTURE FOR 500M ROW ORDERS TABLE                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────┐  Pattern 1: Customer Recent Orders      │
│  │ HOT DATA (< 90 days)    │  ├── Partitioned by month               │
│  │ PostgreSQL Primary       │  ├── Index: (customer_id, created_at)   │
│  │ ~75M rows               │  ├── JPA entity + Spring Data query      │
│  │                          │  └── p95: 20ms                          │
│  └────────────┬─────────────┘                                         │
│               │ CDC                                                    │
│               ▼                                                        │
│  ┌─────────────────────────┐  Pattern 2: Full-Text Search            │
│  │ SEARCH INDEX             │  ├── Elasticsearch cluster              │
│  │ Elasticsearch            │  ├── Denormalized order documents       │
│  │ ~500M documents          │  ├── Updated via CDC (Debezium)        │
│  │                          │  └── p95: 100ms                         │
│  └──────────────────────────┘                                         │
│                                                                        │
│  ┌─────────────────────────┐  Pattern 3: Analytics                   │
│  │ ANALYTICS STORE          │  ├── ClickHouse / TimescaleDB           │
│  │ ClickHouse               │  ├── Pre-aggregated materialized views  │
│  │ ~500M rows (columnar)    │  ├── Fed via CDC                       │
│  │                          │  └── p95: 2s for complex aggregations   │
│  └──────────────────────────┘                                         │
│                                                                        │
│  ┌─────────────────────────┐  Pattern 4: Archive                     │
│  │ COLD STORAGE             │  ├── S3 + Parquet files (by year)       │
│  │ S3 + Athena              │  ├── Queryable via Athena for audits   │
│  │ ~425M rows archived      │  ├── Compressed: 500M rows → ~50GB     │
│  │                          │  └── Query time: 10-60s (acceptable)    │
│  └──────────────────────────┘                                         │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### JPA Role in This Architecture

```java
// JPA handles the HOT DATA (recent orders, OLTP operations)
@Entity
@Table(name = "orders") // Partitioned table (transparent to JPA)
public class Order {
    @Id @GeneratedValue private Long id;
    private Long customerId;
    @Enumerated(STRING) private OrderStatus status;
    private Instant createdAt;
    // ... other fields
}

// Partitioning (done in Flyway, transparent to JPA):
// CREATE TABLE orders (
//     id BIGSERIAL,
//     customer_id BIGINT,
//     created_at TIMESTAMPTZ NOT NULL,
//     ...
// ) PARTITION BY RANGE (created_at);
// 
// CREATE TABLE orders_2024_01 PARTITION OF orders 
//     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

// Repository queries benefit from partition pruning:
@Query("SELECT o FROM Order o WHERE o.customerId = :custId AND o.createdAt > :since")
List<Order> findRecentByCustomer(@Param("custId") Long custId, @Param("since") Instant since);
// PostgreSQL automatically scans only relevant partitions!

// Archive job (moves old data to cold storage)
@Scheduled(cron = "0 0 2 1 * *") // Monthly at 2 AM on the 1st
@Transactional
public void archiveOldOrders() {
    // 1. Export to Parquet → S3
    // 2. DROP PARTITION (instant, no row-by-row delete!)
    // DDL: ALTER TABLE orders DETACH PARTITION orders_2023_01;
    // Then export detached table → S3 → DROP TABLE orders_2023_01;
}
```

### Follow-up Questions
- "How do you handle a query that needs to span hot + cold data?"
- "What's the data consistency model between PostgreSQL and Elasticsearch?"
- "How long does it take for a new order to appear in search?"
- "How do you migrate existing 500M rows into this new architecture?"
- "What's the operational cost comparison?"

---

## Scenario 6: Aggregate Design for Complex Domain

### Problem Statement

**Hospital Management System**. Key operations:
- Schedule appointment (requires: available doctor + available room + valid insurance)
- Admit patient (requires: available bed + assigned doctor + consent forms)
- Record vitals (concurrent: multiple nurses updating same patient chart)
- Create prescription (requires: drug interaction check + doctor authorization)
- Generate bill (requires: all services rendered + insurance verification)

### Aggregate Boundary Analysis

```
WRONG: One giant Patient aggregate
┌────────────────────────────────────────┐
│ Patient (too large!)                    │
│ ├── Demographics                        │
│ ├── List<Appointment> (thousands)       │  Loading Patient loads EVERYTHING
│ ├── List<MedicalRecord> (thousands)     │  Any update locks entire Patient
│ ├── List<Prescription> (hundreds)       │  Multiple concurrent updaters blocked
│ ├── List<LabResult> (hundreds)          │
│ ├── List<Bill> (hundreds)               │
│ └── InsuranceInfo                        │
└────────────────────────────────────────┘

RIGHT: Multiple focused aggregates
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Patient      │  │ Appointment      │  │ MedicalChart     │
│ ├── name     │  │ ├── patientId    │  │ ├── patientId    │
│ ├── dob      │  │ ├── doctorId     │  │ ├── admissionId  │
│ ├── insurance│  │ ├── roomId       │  │ ├── entries[]    │
│ └── contacts │  │ ├── dateTime     │  │ │  ├── vital     │
│              │  │ ├── status       │  │ │  ├── note      │
│              │  │ └── reason       │  │ │  └── recordedBy│
└──────────────┘  └──────────────────┘  │ └── version      │
                                         └──────────────────┘
┌──────────────────┐  ┌──────────────────┐
│ Prescription     │  │ Billing          │
│ ├── patientId    │  │ ├── patientId    │
│ ├── doctorId     │  │ ├── admissionId  │
│ ├── medications[]│  │ ├── lineItems[]  │
│ ├── interactions │  │ ├── insurance    │
│ └── status       │  │ └── status       │
└──────────────────┘  └──────────────────┘
```

### Handling Cross-Aggregate Consistency

```java
// Scheduling appointment requires checking across aggregates:
// - Doctor's schedule (Doctor aggregate)
// - Room availability (Facility aggregate)
// - Patient's insurance validity (Patient aggregate)

@Service
public class AppointmentSchedulingService {
    
    @Transactional
    public Appointment scheduleAppointment(ScheduleRequest request) {
        // 1. Validate patient insurance (read-only check)
        Patient patient = patientRepository.findById(request.getPatientId())
            .orElseThrow();
        if (!patient.hasValidInsurance()) {
            throw new InsuranceExpiredException();
        }
        
        // 2. Check doctor availability (with pessimistic lock to prevent double-booking)
        DoctorSchedule schedule = doctorScheduleRepository
            .findByDoctorIdForUpdate(request.getDoctorId());
        if (!schedule.isAvailable(request.getDateTime(), request.getDuration())) {
            throw new DoctorNotAvailableException();
        }
        
        // 3. Reserve room (with pessimistic lock)
        Room room = roomRepository.findAvailableForUpdate(
            request.getDateTime(), request.getDuration(), request.getRoomType());
        if (room == null) throw new NoRoomAvailableException();
        
        // 4. Create appointment (its own aggregate)
        Appointment appointment = Appointment.schedule(
            request.getPatientId(),
            request.getDoctorId(),
            room.getId(),
            request.getDateTime(),
            request.getDuration()
        );
        
        // 5. Block doctor's time slot
        schedule.blockSlot(request.getDateTime(), request.getDuration(), appointment.getId());
        
        // 6. Reserve room
        room.reserve(request.getDateTime(), request.getDuration(), appointment.getId());
        
        return appointmentRepository.save(appointment);
    }
}

// Concurrent vitals recording (different aggregate per chart entry)
@Service
public class VitalsRecordingService {
    
    @Transactional
    public void recordVitals(Long chartId, VitalsData vitals, String nurseId) {
        // Optimistic locking on MedicalChart - nurses rarely conflict
        MedicalChart chart = chartRepository.findById(chartId)
            .orElseThrow();
        
        chart.addEntry(ChartEntry.vitals(vitals, nurseId, Instant.now()));
        // @Version handles concurrent updates
        // If two nurses update simultaneously: one retries (acceptable)
    }
}
```

---

## Scenario 7: Monolith to Microservices Data Decomposition

### Problem Statement

150 JPA entities, single PostgreSQL database. Extracting User Service first.

### Strangler Fig Approach

```
Phase 1: Identify Boundaries (Week 1-2)
────────────────────────────────────────
Entities belonging to User domain:
├── User, UserProfile, UserPreference, UserRole, Role, Permission
├── Address (shared with Order domain - challenge!)
└── AuditLog (shared with everything - challenge!)

Entities with FK to User:
├── Order.customer_id → User.id
├── Review.author_id → User.id
├── Payment.user_id → User.id
└── 20+ other tables...

Phase 2: API Layer (Week 3-4)
────────────────────────────────────────
Create UserService API that wraps existing JPA repository:
├── Still reads from same database
├── Other services call API instead of direct DB access
├── Introduce anti-corruption layer (DTOs at boundary)
└── Feature flag: route traffic through API vs direct DB

Phase 3: Separate Database (Week 5-8)
────────────────────────────────────────
├── Create new users_db with User domain tables
├── Dual-write: writes go to BOTH old and new DB
├── Read from new DB (with fallback to old)
├── Validate data consistency between old and new
├── Replace FKs with API calls:
│   ├── Order.customer_id stays as BIGINT (no FK constraint)
│   ├── Order service calls User API when it needs user details
│   └── Denormalize frequently-needed data (customer_name on Order)
└── Remove User tables from monolith DB

Phase 4: Cleanup (Week 9-10)
────────────────────────────────────────
├── Remove dual-write (only new DB)
├── Remove old User tables from monolith
├── Remove feature flags
└── Monitor for data inconsistencies
```

### Follow-up Questions
- "How do you handle the Address entity that's shared between User and Order?"
- "What about JOINs that currently span User and Order tables?"
- "How do you handle existing reports that JOIN across domains?"
- "What's your rollback plan if something goes wrong in Phase 3?"
- "How do you maintain referential integrity without FKs?"

---

## Scenario 8: Read-Your-Own-Writes Consistency

### Problem Statement

After microservices split: user places order → redirected to order detail page → sees "No orders found" (because read goes to a replica or event hasn't been processed yet).

### Solution Options

```java
// Option 1: Causal Consistency Token
@PostMapping("/orders")
public ResponseEntity<OrderResponse> createOrder(@RequestBody OrderRequest req) {
    Order order = orderService.create(req);
    
    return ResponseEntity.ok()
        .header("X-Consistency-Token", order.getId() + ":" + order.getVersion())
        .body(OrderResponse.from(order));
}

@GetMapping("/orders/{id}")
public OrderResponse getOrder(
        @PathVariable Long id,
        @RequestHeader(value = "X-Consistency-Token", required = false) String token) {
    
    if (token != null) {
        // Client says "I just wrote this, ensure I can read it"
        // Route to PRIMARY database (not replica)
        return orderService.findByIdFromPrimary(id);
    }
    // Normal read: can use replica (eventual consistency OK)
    return orderService.findById(id);
}

// Option 2: Synchronous confirmation + async side effects
// The order IS confirmed in the primary DB before response
// Only side effects (email, analytics) are async
// So immediate redirect to order detail page reads from primary → works

// Option 3: Optimistic UI (frontend handles it)
// Frontend shows "Order Confirmed" with data it ALREADY has from the POST response
// Doesn't need to re-fetch immediately
// Background poll/websocket for updates
```

---

## Scenario 9: GDPR Compliance Design

### Problem Statement

GDPR Right to Erasure vs 7-year financial record retention.

### Solution: Pseudonymization + Separation

```java
// Separate PII from transactional data
@Entity
@Table(name = "user_pii") // Can be deleted
public class UserPII {
    @Id private Long userId;
    private String fullName;
    private String email;
    private String phone;
    private String address;
    @Enumerated(STRING) private ConsentStatus marketingConsent;
    private Instant consentGrantedAt;
}

@Entity
@Table(name = "orders") // Must be retained 7 years
public class Order {
    @Id private Long id;
    private Long userId;  // After erasure: points to deleted UserPII
    // Denormalized at order time (retained because it's financial record):
    private String customerNameAtOrderTime;  // Pseudonymized on erasure
    private String shippingAddressAtOrderTime; // Pseudonymized on erasure
}

@Service
public class GDPRErasureService {
    
    @Transactional
    public void eraseUser(Long userId) {
        // 1. Delete PII entity completely
        userPIIRepository.deleteById(userId);
        
        // 2. Pseudonymize in financial records (can't delete, but remove PII)
        orderRepository.pseudonymizeCustomerData(userId);
        // UPDATE orders SET customer_name = 'REDACTED', 
        //   shipping_address = 'REDACTED' WHERE user_id = :userId
        
        // 3. Delete from search indexes
        searchService.deleteUserDocuments(userId);
        
        // 4. Delete from caches
        cacheService.evictUser(userId);
        
        // 5. Delete from analytics (or pseudonymize)
        analyticsService.pseudonymize(userId);
        
        // 6. Record erasure for compliance proof
        erasureLogRepository.save(new ErasureLog(userId, Instant.now(), "GDPR request"));
    }
}
```

---

## Scenario 10: Zero-Downtime Column Migration

### Problem Statement

Rename `first_name` + `last_name` → `full_name` on a 200M row `users` table, serving 10K req/s.

### 5-Phase Migration Plan

```
Phase 1: ADD new column (Flyway V1)
──────────────────────────────────────
ALTER TABLE users ADD COLUMN full_name VARCHAR(200);
-- Instant in PostgreSQL 11+ (just metadata change, no table rewrite)
-- JPA entity: unchanged (ignores new column)
-- Risk: ZERO (backward compatible)

Phase 2: DUAL WRITE (App v2 deploy)
──────────────────────────────────────
@Entity
public class User {
    private String firstName;  // Still source of truth
    private String lastName;
    private String fullName;   // Also written now
    
    @PrePersist @PreUpdate
    void syncFullName() {
        this.fullName = firstName + " " + lastName;
    }
}
-- All NEW/UPDATED users have full_name populated
-- Risk: LOW (old data still has null full_name)

Phase 3: BACKFILL (Background job, Flyway V2)
──────────────────────────────────────
-- Run in batches to avoid long lock:
DO $$
DECLARE batch_size INT := 10000;
BEGIN
  LOOP
    UPDATE users SET full_name = first_name || ' ' || last_name
    WHERE full_name IS NULL
    LIMIT batch_size;
    IF NOT FOUND THEN EXIT; END IF;
    COMMIT;  -- Release locks between batches
    PERFORM pg_sleep(0.1);  -- Be nice to production
  END LOOP;
END $$;
-- Verify: SELECT COUNT(*) FROM users WHERE full_name IS NULL; -- Should be 0

Phase 4: SWITCH reads (App v3 deploy)
──────────────────────────────────────
@Entity
public class User {
    private String firstName;  // Still written (backward compat)
    private String lastName;
    private String fullName;   // NOW the source of truth for reads
    
    public String getDisplayName() {
        return fullName;  // Read from new column
    }
}
-- Risk: LOW (can rollback to v2 which reads from old columns)

Phase 5: DROP old columns (Flyway V3, 1 week after v3 stable)
──────────────────────────────────────
ALTER TABLE users DROP COLUMN first_name;
ALTER TABLE users DROP COLUMN last_name;
ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;

@Entity
public class User {
    @Column(nullable = false)
    private String fullName;  // Only column remaining
}
-- Risk: IRREVERSIBLE (ensure v3 is stable before this)
-- Rollback: If needed, v4 Flyway adds columns back from full_name
```

---

## Key Interview Meta-Advice

### How to Structure Your Answer

1. **Clarify requirements** (ask questions before designing)
2. **State assumptions** explicitly
3. **Present 2-3 options** (never just one)
4. **Analyze trade-offs** for EACH option against the specific constraints
5. **Recommend ONE** with clear justification
6. **Acknowledge risks** and mitigation strategies
7. **Discuss evolution** (how does this change at 10x scale?)

### What Interviewers Look For at Staff Level

- **Trade-off thinking**: No solution is perfect; which downsides are acceptable?
- **Constraint awareness**: Different constraints → different optimal solutions
- **Production mindset**: How does this fail? How do you monitor? How do you rollback?
- **Team impact**: Can the team execute this? What's the learning curve?
- **Incremental approach**: How to get there safely, not just the end state
- **Communication**: Can you explain complex decisions to non-technical stakeholders?
