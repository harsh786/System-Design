# Migration & Modernization - Staff Engineer / Architect Level

## Target Level: Staff Engineer / Architect
These problems focus on evolving large-scale systems - the hardest part of being a staff+ engineer. Not greenfield, but transforming running production systems with zero downtime.

---

## Problem 1: Migrate a Monolithic Spring MVC App to Microservices

**Scenario:** You have a 500K-line Spring MVC monolith (Java 8, Spring Boot 1.5):
- 200 REST endpoints, 80 database tables, 50 scheduled jobs
- 30 developers across 5 teams working on it
- Deployment takes 45 minutes, happens once a week
- Frequent merge conflicts, test suite takes 2 hours
- Tightly coupled: changing one module breaks others

**Questions:**

### Q1: How do you decompose this monolith? What's your strategy?

**Expected Discussion:**
```
Phase 1: Strangler Fig Pattern (NOT big-bang rewrite)
  - Identify bounded contexts (DDD)
  - Extract services one at a time, starting with:
    a. Least coupled module (e.g., notifications)
    b. Most-changing module (reduces merge conflicts first)
    c. Performance-critical module (benefits most from isolation)

  ┌────────────────────────────────────────────────────┐
  │                    API Gateway                       │
  │  /api/notifications → New Notification Service      │
  │  /api/*             → Monolith (everything else)    │
  └────────────────────────────────────────────────────┘

Phase 2: Database Decomposition (hardest part)
  - Shared database → Service owns its data
  - Strategies:
    a. Database view for read compatibility
    b. Change Data Capture (Debezium) for sync
    c. Dual-write with verification (temporary)
    d. Eventual consistency via events

Phase 3: Incremental extraction
  - One bounded context at a time
  - Each extraction includes: API, data, async jobs
  - Keep monolith shrinking, never growing
```

### Q2: How do you handle the shared database problem?

```
Current State:
  ┌──────────────┐
  │   Monolith   │──→ Single Database (80 tables)
  └──────────────┘    All services query any table

Target State:
  ┌───────────┐  ┌───────────┐  ┌───────────┐
  │ Orders    │  │ Users     │  │ Products  │
  │ Service   │  │ Service   │  │ Service   │
  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │Orders DB│    │Users DB │    │Prods DB │
   └─────────┘    └─────────┘    └─────────┘

Migration Strategy (per service extraction):
  Step 1: Mark table ownership (which service owns which tables)
  Step 2: Create API for cross-service data access
  Step 3: Migrate direct table access → API calls (in monolith)
  Step 4: Extract tables to new database
  Step 5: Use CDC or events for denormalized views

The JOIN Problem:
  - Monolith: SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.id
  - Microservices: Can't join across databases!
  
  Solutions:
  a. API composition (fetch from both services, join in-memory)
  b. Denormalized view (store user_name in orders DB, sync via events)
  c. CQRS read model (materialized view for queries)
```

### Q3: How do you migrate without downtime?

```
Zero-Downtime Migration Steps:

1. Build new service alongside monolith
2. Route traffic: Gateway sends to BOTH (shadow traffic to new)
3. Compare responses (verification period)
4. Gradual cutover (1% → 10% → 50% → 100%)
5. Remove old code from monolith

Feature Flags for Migration:
  @GetMapping("/api/orders/{id}")
  public Order getOrder(@PathVariable Long id) {
      if (featureFlag.isEnabled("use-order-service", user)) {
          return orderServiceClient.getOrder(id);  // New service
      }
      return localOrderService.getOrder(id);  // Monolith code
  }

Data Migration with Dual-Write:
  Phase 1: Write to OLD, async replicate to NEW
  Phase 2: Write to BOTH (verify consistency)
  Phase 3: Write to NEW, async replicate to OLD (rollback safety)
  Phase 4: Write to NEW only, decommission OLD
```

---

## Problem 2: Upgrade from Spring Boot 2.x to 3.x (Java 8 → 21)

**Scenario:** You have 80 microservices on Spring Boot 2.7 / Java 11:
- Critical production systems (payments, orders, inventory)
- 15 shared libraries used across services
- Mix of REST, messaging (Kafka), scheduled jobs
- javax.* namespace throughout (needs jakarta.* migration)
- Some services use Spring Security 5 with custom OAuth2 flow

**Questions:**

### Q4: What's your migration strategy for 80 services?

**Expected Approach:**
```
Strategy: Bottom-Up, Library-First

Phase 1: Upgrade Shared Libraries (2-4 weeks)
  - Upgrade shared libs to be DUAL-COMPATIBLE (javax + jakarta)
  - Use multi-release JARs or abstraction layers
  - All services can still use these libs on Boot 2.7

Phase 2: Pilot Migration (2-3 services, 2 weeks)
  - Pick non-critical services first
  - Document every breaking change encountered
  - Create migration playbook

Phase 3: Automated Migration Tooling (1-2 weeks)
  - OpenRewrite recipes for javax → jakarta
  - Custom recipes for Spring Security migration
  - CI pipeline that runs migration + tests
  - Script: upgrade pom/gradle → run OpenRewrite → run tests → PR

Phase 4: Wave-based Migration (8-12 weeks)
  - Wave 1: Non-critical services (20 services)
  - Wave 2: Medium-criticality (30 services)
  - Wave 3: High-criticality (20 services)
  - Wave 4: Critical path (10 services)
  - Each wave: 1 week migration + 1 week soak

Phase 5: Adopt Java 21 Features (ongoing)
  - Virtual threads (spring.threads.virtual.enabled=true)
  - Record patterns, sealed classes
  - Structured concurrency (preview)
```

### Q5: How do you handle the javax to jakarta namespace migration?

```java
// OpenRewrite recipe handles most automated changes:
// javax.servlet.* → jakarta.servlet.*
// javax.persistence.* → jakarta.persistence.*
// javax.validation.* → jakarta.validation.*
// javax.annotation.* → jakarta.annotation.*

// But MANUAL fixes needed for:

// 1. Custom servlet filters
// Before (javax):
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.ServletRequest;

// After (jakarta):
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletRequest;

// 2. JPA entities
// Before: import javax.persistence.*;
// After: import jakarta.persistence.*;

// 3. Validation annotations
// Before: import javax.validation.constraints.*;
// After: import jakarta.validation.constraints.*;

// 4. Third-party libraries that still use javax
// Problem: Some libs not yet migrated
// Solution: Use jakarta-to-javax bridge OR upgrade the library

// 5. Spring Security migration (MAJOR changes)
// Before (Spring Security 5):
@Override
protected void configure(HttpSecurity http) throws Exception {
    http.authorizeRequests()
        .antMatchers("/api/**").authenticated();
}

// After (Spring Security 6):
@Bean
public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http.authorizeHttpRequests(auth -> auth
        .requestMatchers("/api/**").authenticated());
    return http.build();
}
```

### Q6: How do you handle the shared library dependency hell?

```
Problem: Service A needs lib v2 (Boot 3), Service B needs lib v1 (Boot 2)
During migration, both versions must coexist.

Solutions:

1. Dual-Version Libraries:
   my-shared-lib-1.x  → Spring Boot 2.x compatible
   my-shared-lib-2.x  → Spring Boot 3.x compatible
   Maintain both during migration window

2. Abstraction Layer:
   my-shared-lib-api       (interfaces only, no Spring deps)
   my-shared-lib-boot2     (Boot 2 implementation)
   my-shared-lib-boot3     (Boot 3 implementation)

3. BOM (Bill of Materials) per Spring Boot version:
   platform-bom-boot2.xml  → All lib versions for Boot 2
   platform-bom-boot3.xml  → All lib versions for Boot 3
   Each service picks the right BOM

CI/CD Considerations:
  - Shared lib PRs must pass tests against BOTH Boot versions
  - Feature branches can upgrade individual services
  - Canary deployment after each service upgrade
  - Rollback plan: revert to previous Boot 2 artifact
```

---

## Problem 3: Migrate from Spring MVC to WebFlux

**Scenario:** A high-traffic API service (50K rps) needs to move from Spring MVC to WebFlux:
- Currently uses JDBC (PostgreSQL), RestTemplate, Spring Security
- Has 40 endpoints, extensive test suite
- Must maintain backward compatibility during migration
- Cannot have downtime or performance regression

**Questions:**

### Q7: When is this migration actually justified vs just adding more instances?

```
JUSTIFY MIGRATION when:
  ✓ I/O-bound workload (lots of HTTP calls, DB queries per request)
  ✓ High connection count (>10K concurrent)
  ✓ Cost optimization needed (fewer instances for same load)
  ✓ Streaming requirements (SSE, WebSocket at scale)
  ✓ Already using reactive database drivers is feasible

DO NOT MIGRATE when:
  ✗ CPU-bound workload (WebFlux won't help)
  ✗ Simple CRUD with low concurrency
  ✗ Team doesn't have reactive experience
  ✗ Heavy use of ThreadLocal (MDC, security context)
  ✗ JPA/Hibernate dependency (no reactive equivalent)
  ✗ Virtual Threads (Java 21) would solve the problem simpler

Cost Comparison (50K rps, I/O bound):
  Spring MVC: 25 instances × $200/month = $5,000/month
  Spring WebFlux: 5 instances × $200/month = $1,000/month
  Virtual Threads: 8 instances × $200/month = $1,600/month

  If cost matters AND team is skilled: WebFlux
  If simplicity matters: Virtual Threads
```

### Q8: What's the migration path from JDBC to R2DBC?

```
Phase 1: Introduce WebFlux alongside MVC
  - Add spring-boot-starter-webflux dependency
  - Create new reactive endpoints (parallel to existing)
  - Both stacks CAN run on Tomcat (but not ideal)

Phase 2: Migrate HTTP clients
  - RestTemplate → WebClient (works in MVC too)
  - This is safe, WebClient works in blocking context

Phase 3: Migrate to R2DBC (HARDEST)
  - Can't use JPA entities directly
  - No lazy loading in R2DBC
  - No joins (must compose at application level)
  
  Strategy:
  a. Keep JDBC for complex queries (on boundedElastic scheduler)
  b. Migrate simple CRUD to R2DBC first
  c. For complex queries: use DatabaseClient with manual mapping

  // Adapter pattern during migration:
  @Service
  public class UserService {
      @Autowired private UserJdbcRepository jdbcRepo;  // Old
      @Autowired private UserR2dbcRepository r2dbcRepo; // New
      
      public Mono<User> findById(Long id) {
          if (featureFlag.isEnabled("r2dbc-users")) {
              return r2dbcRepo.findById(id);
          }
          return Mono.fromCallable(() -> jdbcRepo.findById(id).orElseThrow())
              .subscribeOn(Schedulers.boundedElastic());
      }
  }

Phase 4: Switch embedded server
  - Tomcat → Netty (remove servlet dependency)
  - This is when you get the full event-loop benefit

Phase 5: Migrate remaining blocking code
  - Spring Security reactive configuration
  - Reactive cache (Caffeine → Reactor cache)
  - Reactive Kafka consumer/producer
```

---

## Problem 4: Migrate to Kubernetes from VM-based Deployment

**Scenario:** Your team runs 40 Spring Boot services on VMs (EC2):
- Each service deployed via Ansible to dedicated VMs
- Auto-scaling via ASG (slow: 3-5 min to scale)
- Service discovery via Consul
- Configuration via Spring Cloud Config Server
- Logging via ELK stack on VMs

**Questions:**

### Q9: What's the migration strategy to Kubernetes?

```
Phase 1: Containerize (2-4 weeks)
  - Create Dockerfiles for all services
  - Optimize: multi-stage builds, JRE-only images
  - Container registry (ECR/GCR)
  - Run containers on VMs first (Docker Compose for dev)

Phase 2: Platform Setup (2-4 weeks)
  - EKS/GKE/AKS cluster setup
  - Networking (VPC, ingress, service mesh consideration)
  - Secrets management (External Secrets Operator → AWS Secrets Manager)
  - CI/CD pipeline (build → push → deploy to K8s)

Phase 3: Non-Critical Migration (4-6 weeks)
  - Migrate batch/async services first (lower risk)
  - Replace Consul with Kubernetes Service Discovery
  - Replace Spring Cloud Config with ConfigMaps/Secrets
  - Set up HPA (Horizontal Pod Autoscaler)

Phase 4: Traffic Migration (4-6 weeks)
  - DNS-based cutover (weighted routing)
  - Run in parallel: VM + K8s (same service, split traffic)
  - Gradually shift traffic: 10% → 50% → 100%
  - Keep VM deployment as rollback for 2 weeks

Phase 5: Critical Services (4 weeks)
  - Payment, order services (extra caution)
  - Blue-green deployment within K8s
  - Extensive load testing before cutover
  - Runbook for rollback to VMs
```

### Q10: What Spring Boot configurations must change for Kubernetes?

```yaml
# application-kubernetes.yml

# 1. Graceful Shutdown (critical for rolling updates)
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s

# 2. Health Probes (Kubernetes native)
management:
  endpoint:
    health:
      probes:
        enabled: true  # Enables /actuator/health/liveness and /readiness
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true

# 3. Service Discovery (no more Consul)
# Use Kubernetes DNS: http://payment-service.default.svc.cluster.local:8080
# Or with Spring Cloud Kubernetes:
spring:
  cloud:
    kubernetes:
      discovery:
        enabled: true

# 4. Configuration (ConfigMap/Secret mounted)
spring:
  config:
    import: optional:configtree:/etc/config/

# 5. JVM settings for containers
# Set via JAVA_OPTS env var in deployment:
# -XX:MaxRAMPercentage=75.0
# -XX:+UseG1GC
# -XX:+ExitOnOutOfMemoryError (let K8s restart)
```

---

## Problem 5: Adopt Event-Driven Architecture in a Synchronous System

**Scenario:** You have a synchronous request-response architecture:
- Order service calls Payment, Inventory, Shipping, Notification synchronously
- Average response time: 800ms (sum of all downstream calls)
- Single failure cascades to all users
- Cannot handle traffic spikes (everything is coupled)

### Q11: How do you introduce event-driven patterns incrementally?

```
Current (synchronous chain):
  User → Order → Payment → Inventory → Shipping → Notification
  Total latency: 100 + 200 + 150 + 200 + 150 = 800ms
  If Payment is slow: EVERYTHING is slow

Target (event-driven):
  User → Order (200ms response)
         ├── Publish OrderCreated event
         │    ├── PaymentConsumer (async)
         │    ├── InventoryConsumer (async)
         │    └── NotificationConsumer (async)
         └── Return order ID immediately

Migration Steps:

Step 1: Introduce Kafka (infrastructure)
  - Set up Kafka cluster
  - Schema Registry for event schemas
  - Team training on event-driven patterns

Step 2: Start with Notifications (lowest risk)
  - Before: orderService.createOrder() calls notificationService.send()
  - After: orderService publishes OrderCreated → NotificationConsumer listens
  - If consumer fails: notification delayed, not order failure

Step 3: Move to Inventory
  - Event: OrderCreated → InventoryConsumer reserves stock
  - Response: InventoryReserved or InventoryFailed event
  - Order service listens for result, updates status

Step 4: Payment (most sensitive)
  - Implement saga pattern with compensation
  - OrderCreated → PaymentConsumer → PaymentSucceeded/PaymentFailed
  - On failure: compensate previous steps

Step 5: Real-time order tracking
  - SSE/WebSocket endpoint for customers
  - Each event updates order status
  - Customer sees: Order Placed → Payment Confirmed → Shipped
```

### Q12: How do you maintain data consistency in the async world?

```
The Consistency Challenge:
  Sync: begin TX → debit → credit → commit (ACID)
  Async: publish event → consumer processes → what if consumer fails?

Patterns for Consistency:

1. Outbox Pattern (most common):
   @Transactional
   public Order createOrder(OrderRequest req) {
       Order order = orderRepo.save(new Order(req));
       outboxRepo.save(new OutboxEvent("OrderCreated", order.toEvent()));
       return order;  // Order + Event in SAME transaction
   }
   // Separate process: read outbox → publish to Kafka → mark published

2. Change Data Capture (Debezium):
   - Captures database changes as events
   - No application code changes needed
   - INSERT into orders → Kafka event automatically
   - Guaranteed delivery (from WAL/binlog)

3. Saga with State Machine:
   PENDING → PAYMENT_PENDING → PAID → INVENTORY_RESERVED → SHIPPED
                              → PAYMENT_FAILED → CANCELLED
   
   Each state transition is idempotent
   Timeout handling: if stuck in PAYMENT_PENDING > 5min → compensate

4. Eventual Consistency Verification:
   - Reconciliation job: compare source of truth vs derived state
   - Run periodically: "orders in PAID but no inventory reservation after 5min"
   - Alert + auto-fix or manual intervention
```

---

## Problem 6: Performance Migration - Achieving 10x Throughput

**Scenario:** Your API service handles 5K rps and needs to handle 50K rps:
- Current: Spring MVC, PostgreSQL (JDBC), 20 EC2 instances
- Budget allows only 2x infrastructure increase
- Must achieve 10x throughput with 2x resources (5x efficiency)

### Q13: What's your optimization strategy?

```
Layer-by-Layer Optimization:

1. APPLICATION LAYER (3x improvement):
   - Enable virtual threads (Java 21) → handles 10x concurrent requests per thread
   - OR migrate to WebFlux (if team ready)
   - Optimize serialization (switch to Jackson afterburner/blackbird)
   - Remove unnecessary middleware (every filter adds latency)
   - Async for non-critical operations (logging, metrics, notifications)

2. DATABASE LAYER (2-3x improvement):
   - Add read replicas (route reads to replicas)
   - Connection pool tuning (HikariCP optimization)
   - Query optimization (N+1, missing indexes, explain analyze)
   - Caching layer (Redis for hot data, reduce DB load by 70%)
   - Prepared statement caching

3. NETWORK LAYER (1.5-2x improvement):
   - HTTP/2 (multiplexing, fewer connections)
   - gRPC for internal service communication
   - Connection pooling for downstream HTTP calls
   - Compress responses (gzip/brotli)

4. JVM LAYER (1.2-1.5x improvement):
   - GC tuning (ZGC for low latency or G1 with tuned regions)
   - JVM warm-up (CDS, AOT compilation)
   - Right-size heap (too large = long GC pauses)

5. INFRASTRUCTURE (2x, already budgeted):
   - More instances
   - Better hardware (compute optimized)
   - CDN for static content
   - Auto-scaling for peak handling

Combined: 3 × 2.5 × 1.5 × 1.3 × 2 ≈ 29x theoretical
Realistic: 10-15x achievable (contention, Amdahl's law)
```

### Q14: How do you measure and validate the improvements?

```
Performance Testing Framework:

1. Baseline Measurement:
   - Load test with Gatling/k6 at current traffic (5K rps)
   - Capture: p50, p95, p99, max latency, error rate, CPU, memory
   - Create performance budget per endpoint

2. Progressive Load Testing:
   - Ramp: 5K → 10K → 20K → 30K → 50K rps
   - At each level: observe degradation point
   - Identify bottleneck: CPU? Memory? DB connections? Network?

3. Profiling Tools:
   - async-profiler (flame graphs for CPU/allocation hotspots)
   - JFR (Java Flight Recorder) for production profiling
   - Spring Boot Actuator + Micrometer for endpoint-level metrics

4. Automated Performance Regression:
   - Run load tests in CI/CD
   - Compare against performance budget
   - Fail deploy if p99 > threshold

5. Production Validation:
   - Canary deployment with performance monitoring
   - Compare canary metrics vs baseline
   - Auto-rollback if degradation detected
```
