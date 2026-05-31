# Platform Engineering & Multi-Tenancy - Staff Engineer / Architect Level

## Target Level: Staff Engineer / Architect
These problems focus on building internal platforms and multi-tenant systems -- the leverage multiplier work that defines staff+ engineering.

---

## Problem 1: Build an Internal Developer Platform

**Scenario:** Your organization has 50 teams, 200 services. Each team spends 30% of time on:
- Setting up new services (boilerplate, CI/CD, observability)
- Managing infrastructure (Kubernetes manifests, secrets, configs)
- Operational toil (debugging, on-call runbooks, deployments)

Goal: Reduce this to 5% by building a platform.

### Q1: What does an Internal Developer Platform provide?

```
INTERNAL DEVELOPER PLATFORM LAYERS:

┌─────────────────────────────────────────────────────────────────┐
│  DEVELOPER EXPERIENCE LAYER (Self-Service Portal)                │
│  ├── Service Catalog (create new service in 5 minutes)          │
│  ├── Deployment Dashboard (one-click deploy, rollback)          │
│  ├── Observability Portal (logs, metrics, traces unified)       │
│  └── Documentation Hub (auto-generated, searchable)             │
└───────────────────────────────────────────────────────────────┬─┘
                                                                 │
┌─────────────────────────────────────────────────────────────────┐
│  PLATFORM SERVICES LAYER                                         │
│  ├── Service Template Engine (Spring Boot archetype)            │
│  ├── CI/CD Pipeline (build, test, deploy, rollback)             │
│  ├── Config Management (hierarchical, secrets)                  │
│  ├── Service Mesh (mTLS, traffic management)                    │
│  ├── API Gateway (routing, rate limiting, auth)                 │
│  └── Event Platform (Kafka, schema registry)                    │
└───────────────────────────────────────────────────────────────┬─┘
                                                                 │
┌─────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER (abstracted from developers)               │
│  ├── Kubernetes (auto-provisioned, multi-cluster)               │
│  ├── Databases (managed, provisioned via API)                   │
│  ├── Caching (Redis clusters, auto-scaled)                      │
│  └── Storage (S3/Blob, CDN)                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Q2: How do you build a Spring Boot Service Template (Golden Path)?

```java
// The "Golden Path" - opinionated service template that includes everything

// Custom Spring Boot Starter: company-spring-boot-starter
// Includes: observability, security, error handling, health checks, standards

// pom.xml for the starter:
<dependencies>
    <!-- Core Spring Boot -->
    <dependency>spring-boot-starter-webflux</dependency>
    <dependency>spring-boot-starter-actuator</dependency>
    
    <!-- Observability (pre-configured) -->
    <dependency>micrometer-tracing-bridge-otel</dependency>
    <dependency>opentelemetry-exporter-otlp</dependency>
    <dependency>micrometer-registry-prometheus</dependency>
    
    <!-- Security (company OAuth2 pre-configured) -->
    <dependency>spring-boot-starter-oauth2-resource-server</dependency>
    <dependency>company-security-starter</dependency>
    
    <!-- Resilience -->
    <dependency>resilience4j-spring-boot3</dependency>
    
    <!-- Standards enforcement -->
    <dependency>company-api-standards</dependency>
</dependencies>

// Auto-configuration in the starter:
@AutoConfiguration
@ConditionalOnWebApplication(type = REACTIVE)
public class CompanyWebAutoConfiguration {
    
    // Standardized error handling
    @Bean
    @ConditionalOnMissingBean
    public GlobalErrorHandler globalErrorHandler() {
        return new GlobalErrorHandler(); // RFC 7807 format
    }
    
    // Request/response logging
    @Bean
    @ConditionalOnProperty("company.logging.requests.enabled", havingValue = "true", matchIfMissing = true)
    public RequestLoggingFilter requestLoggingFilter() {
        return new RequestLoggingFilter();
    }
    
    // Standardized health checks
    @Bean
    public CompanyHealthIndicator companyHealthIndicator(
            ApplicationContext context) {
        return new CompanyHealthIndicator(context);
    }
    
    // Metrics naming conventions
    @Bean
    public MeterFilter companyMeterFilter() {
        return new MeterFilter() {
            @Override
            public Meter.Id map(Meter.Id id) {
                // Enforce: all custom metrics prefixed with service name
                return id;
            }
        };
    }
    
    // Security defaults
    @Bean
    @ConditionalOnMissingBean(SecurityFilterChain.class)
    public SecurityFilterChain defaultSecurityChain(HttpSecurity http) throws Exception {
        http.oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health/**").permitAll()
                .requestMatchers("/actuator/prometheus").permitAll()
                .anyRequest().authenticated());
        return http.build();
    }
}

// Service template generator (Yeoman/cookiecutter equivalent):
// POST /platform/api/services/create
{
    "name": "order-service",
    "team": "payments",
    "type": "webflux-api",    // Options: webflux-api, kafka-consumer, batch-job
    "database": "postgresql",
    "messaging": "kafka",
    "features": ["caching", "scheduling"]
}

// Generates:
// - Spring Boot project with company starter
// - Dockerfile (optimized)
// - Kubernetes manifests (Helm chart)
// - CI/CD pipeline (GitHub Actions/Jenkins)
// - Terraform for infrastructure (DB, Redis, Kafka topics)
// - Grafana dashboards (pre-configured)
// - PagerDuty integration
// - README with runbook
```

### Q3: How do you enforce standards without blocking teams?

```
ENFORCEMENT SPECTRUM:

Hard Enforcement (blocks deployment):
  - Security vulnerabilities (CVE in dependencies)
  - No health checks defined
  - No tracing configured
  - Authentication not implemented
  - Resource limits not set in K8s manifests

Soft Enforcement (warns, tracks, nudges):
  - API lint violations (style guide)
  - Missing documentation
  - Test coverage below threshold
  - Non-standard patterns detected
  - Performance budget violations

Implementation:

// CI/CD Gate: Platform compliance check
@Service
public class ComplianceChecker {
    
    public ComplianceReport check(ServiceManifest manifest) {
        ComplianceReport report = new ComplianceReport();
        
        // HARD BLOCKS
        report.addCheck("health-endpoint", checkHealthEndpoint(manifest));
        report.addCheck("security-config", checkSecurityConfig(manifest));
        report.addCheck("resource-limits", checkResourceLimits(manifest));
        report.addCheck("tracing-enabled", checkTracingEnabled(manifest));
        
        // SOFT WARNINGS
        report.addWarning("api-lint", runApiLinter(manifest));
        report.addWarning("test-coverage", checkTestCoverage(manifest));
        report.addWarning("documentation", checkDocs(manifest));
        
        return report;
    }
}

// Scoring system (gamification for adoption):
Service Score Card:
  ├── Security: 95/100 (green)
  ├── Observability: 88/100 (green)
  ├── Reliability: 72/100 (yellow) - missing chaos testing
  ├── Documentation: 60/100 (orange) - stale API docs
  └── Overall: B+ (visible on platform dashboard)
```

---

## Problem 2: Multi-Tenant Architecture

**Scenario:** You're building a B2B SaaS platform where:
- 500 tenants (companies) use the same system
- Tenants range from 10 users to 100K users
- Data MUST be isolated (regulatory requirement)
- Some tenants need dedicated resources (premium tier)
- System must scale to 10K tenants

### Q4: What are the multi-tenancy isolation models?

```
ISOLATION MODELS:

1. SHARED EVERYTHING (Pool model):
   ┌─────────────────────────────────────┐
   │  Shared App Instances                │
   │  Shared Database                     │
   │  tenant_id column on every table    │
   └─────────────────────────────────────┘
   
   Pros: Cheapest, easy to deploy, efficient resource usage
   Cons: Noisy neighbor risk, harder compliance, complex queries
   Best for: Small tenants, SaaS startups, non-regulated industries

2. SHARED APP, SEPARATE DATABASE (Schema/DB per tenant):
   ┌─────────────────────────────────────┐
   │  Shared App Instances                │
   │  ┌────────┐ ┌────────┐ ┌────────┐  │
   │  │Tenant A│ │Tenant B│ │Tenant C│  │
   │  │  DB    │ │  DB    │ │  DB    │  │
   │  └────────┘ └────────┘ └────────┘  │
   └─────────────────────────────────────┘
   
   Pros: Data isolation, easy backup/restore per tenant, compliance friendly
   Cons: Connection pool per tenant (limited), schema migration complexity
   Best for: Regulated industries, medium tenants, data sovereignty

3. DEDICATED EVERYTHING (Silo model):
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │  Tenant A  │ │  Tenant B  │ │  Tenant C  │
   │  App + DB  │ │  App + DB  │ │  App + DB  │
   │  (isolated)│ │  (isolated)│ │  (isolated)│
   └────────────┘ └────────────┘ └────────────┘
   
   Pros: Complete isolation, dedicated scaling, easy to customize
   Cons: Most expensive, operational overhead, slow onboarding
   Best for: Enterprise tenants, high-security, premium tier

4. HYBRID (recommended for most):
   ┌─────────────────────────────────────┐
   │  Free/Standard Tier: Shared pool    │
   │  (row-level isolation, shared DB)   │
   ├─────────────────────────────────────┤
   │  Premium Tier: Dedicated DB         │
   │  (schema-per-tenant, shared app)    │
   ├─────────────────────────────────────┤
   │  Enterprise Tier: Fully dedicated   │
   │  (separate cluster, custom config)  │
   └─────────────────────────────────────┘
```

### Q5: How do you implement multi-tenancy in Spring Boot?

```java
// APPROACH: Row-level isolation with tenant context

// 1. Tenant Resolution (from JWT, subdomain, or header)
@Component
public class TenantResolver implements WebFilter {
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String tenantId = resolveTenant(exchange);
        return chain.filter(exchange)
            .contextWrite(Context.of("tenantId", tenantId));
    }
    
    private String resolveTenant(ServerWebExchange exchange) {
        // Strategy 1: From JWT claims
        JwtAuthenticationToken auth = exchange.getPrincipal().block();
        if (auth != null) {
            return auth.getToken().getClaimAsString("tenant_id");
        }
        
        // Strategy 2: From subdomain
        String host = exchange.getRequest().getHeaders().getHost().getHostName();
        return host.split("\\.")[0]; // tenant1.app.com → tenant1
        
        // Strategy 3: From header
        return exchange.getRequest().getHeaders().getFirst("X-Tenant-ID");
    }
}

// 2. Tenant Context (available throughout request)
public class TenantContext {
    private static final ThreadLocal<String> currentTenant = new ThreadLocal<>();
    
    public static void setTenantId(String tenantId) {
        currentTenant.set(tenantId);
    }
    
    public static String getTenantId() {
        String tenant = currentTenant.get();
        if (tenant == null) {
            throw new TenantNotResolvedException("No tenant in context");
        }
        return tenant;
    }
    
    public static void clear() {
        currentTenant.remove();
    }
}

// 3. Row-Level Security (automatic tenant filtering)
// Option A: Hibernate Filter (JPA)
@Entity
@Table(name = "orders")
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Order {
    @Id private String id;
    
    @Column(name = "tenant_id", nullable = false)
    private String tenantId;
    
    private String customerId;
    private BigDecimal amount;
}

// Enable filter for every request
@Component
public class TenantFilterAspect {
    @Autowired private EntityManager em;
    
    @Around("execution(* com.example.repository.*.*(..))")
    public Object applyTenantFilter(ProceedingJoinPoint pjp) throws Throwable {
        Session session = em.unwrap(Session.class);
        session.enableFilter("tenantFilter")
            .setParameter("tenantId", TenantContext.getTenantId());
        return pjp.proceed();
    }
}

// Option B: Spring Data R2DBC with tenant context
@Repository
public class TenantAwareOrderRepository {
    private final DatabaseClient client;
    
    public Flux<Order> findAll() {
        return Mono.deferContextual(ctx -> {
            String tenantId = ctx.get("tenantId");
            return client.sql("SELECT * FROM orders WHERE tenant_id = :tenant")
                .bind("tenant", tenantId)
                .map(this::mapRow)
                .all();
        });
    }
    
    public Mono<Order> save(Order order) {
        return Mono.deferContextual(ctx -> {
            order.setTenantId(ctx.get("tenantId")); // Ensure correct tenant
            return client.sql("INSERT INTO orders ...")
                .bind("tenant_id", order.getTenantId())
                .fetch().rowsUpdated()
                .thenReturn(order);
        });
    }
}

// 4. Database-per-tenant (for premium tier)
@Configuration
public class MultiTenantDataSourceConfig {
    
    @Bean
    public DataSource dataSource() {
        return new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                String tenantId = TenantContext.getTenantId();
                TenantConfig config = tenantRegistry.getConfig(tenantId);
                
                if (config.getTier() == Tier.PREMIUM) {
                    return "dedicated-" + tenantId; // Separate DB
                }
                return "shared-pool"; // Shared DB
            }
        };
    }
}
```

### Q6: How do you prevent noisy neighbor problems?

```java
// NOISY NEIGHBOR: One tenant consuming disproportionate resources
// affecting all other tenants

// Solution 1: Per-tenant rate limiting
@Component
public class TenantRateLimiter implements WebFilter {
    private final Map<String, RateLimiter> limiters = new ConcurrentHashMap<>();
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String tenantId = resolveTenant(exchange);
        TenantConfig config = tenantRegistry.getConfig(tenantId);
        
        RateLimiter limiter = limiters.computeIfAbsent(tenantId, id ->
            RateLimiter.of(id, RateLimiterConfig.custom()
                .limitForPeriod(config.getRateLimit())    // e.g., 1000 rps for premium
                .limitRefreshPeriod(Duration.ofSeconds(1))
                .timeoutDuration(Duration.ofMillis(100))
                .build()));
        
        if (limiter.acquirePermission()) {
            return chain.filter(exchange);
        }
        
        exchange.getResponse().setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
        return exchange.getResponse().setComplete();
    }
}

// Solution 2: Per-tenant connection pool limits
@Service
public class TenantAwareConnectionPool {
    // Each tenant gets a bounded slice of the connection pool
    // Premium: 20 connections, Standard: 5 connections, Free: 2 connections
    
    private final Map<String, Semaphore> tenantSemaphores = new ConcurrentHashMap<>();
    
    public Connection getConnection(String tenantId) {
        TenantConfig config = tenantRegistry.getConfig(tenantId);
        Semaphore semaphore = tenantSemaphores.computeIfAbsent(
            tenantId, id -> new Semaphore(config.getMaxConnections()));
        
        if (!semaphore.tryAcquire(5, TimeUnit.SECONDS)) {
            throw new ResourceExhaustedException(
                "Tenant " + tenantId + " connection limit reached");
        }
        
        try {
            return dataSource.getConnection();
        } catch (Exception e) {
            semaphore.release();
            throw e;
        }
    }
}

// Solution 3: Per-tenant compute isolation (Kubernetes)
// Premium tenants get dedicated pods via node affinity:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service-tenant-acme
spec:
  template:
    spec:
      nodeSelector:
        tenant: acme  # Dedicated nodes for premium tenant
      containers:
        - name: order-service
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
            limits:
              cpu: "4"
              memory: "8Gi"

// Solution 4: Request prioritization
@Component
public class TenantPriorityFilter implements WebFilter {
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String tenantId = resolveTenant(exchange);
        TenantConfig config = tenantRegistry.getConfig(tenantId);
        
        // Route premium tenants to dedicated thread pool
        if (config.getTier() == Tier.PREMIUM) {
            return chain.filter(exchange)
                .subscribeOn(Schedulers.fromExecutor(premiumExecutor));
        }
        
        return chain.filter(exchange); // Default event loop
    }
}
```

---

## Problem 3: Build a Shared Library Strategy

### Q7: How do you manage shared libraries across 200 services?

```
SHARED LIBRARY STRATEGY:

TYPES OF SHARED CODE:
  1. Platform Libraries (company-spring-boot-starter)
     - Observability, security, error handling
     - Maintained by platform team
     - REQUIRED for all services

  2. Domain Libraries (payment-models, user-contracts)
     - Shared DTOs, API contracts
     - Maintained by domain team
     - Used by consumers of that domain

  3. Utility Libraries (company-utils)
     - Common utilities, helpers
     - Maintained by platform team
     - OPTIONAL, convenience only

VERSIONING & DEPENDENCY MANAGEMENT:

// BOM (Bill of Materials) - controls all versions centrally
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.company</groupId>
            <artifactId>platform-bom</artifactId>
            <version>2024.3.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

// platform-bom defines compatible versions:
<properties>
    <spring-boot.version>3.2.3</spring-boot.version>
    <company-security.version>2.1.0</company-security.version>
    <company-observability.version>1.5.0</company-observability.version>
    <company-commons.version>3.0.0</company-commons.version>
</properties>

UPGRADE STRATEGY:
  1. Library team releases new version
  2. Automated PR bot creates upgrade PRs for all services
  3. Services run tests automatically
  4. Teams have 30 days to merge (for non-security updates)
  5. Security patches: 7-day mandatory window
  6. Tracking dashboard shows adoption across fleet

AVOIDING LIBRARY HELL:
  ✅ Keep libraries SMALL and focused
  ✅ Minimize transitive dependencies
  ✅ Use interfaces/SPI for extensibility
  ✅ Semantic versioning strictly
  ✅ Backward compatibility for 2 major versions
  ❌ Don't put business logic in shared libs
  ❌ Don't share database models across services
  ❌ Don't create "god" utility libraries
```

---

## Problem 4: Tenant Onboarding and Lifecycle

### Q8: How do you design automated tenant provisioning?

```java
// Tenant Onboarding Pipeline

@Service
public class TenantProvisioningService {
    
    @Transactional
    public Mono<TenantProvisionResult> provisionTenant(TenantRequest request) {
        return validateRequest(request)
            .flatMap(this::createTenantRecord)
            .flatMap(this::provisionDatabase)
            .flatMap(this::provisionInfrastructure)
            .flatMap(this::configureSecurityRealm)
            .flatMap(this::seedInitialData)
            .flatMap(this::enableMonitoring)
            .flatMap(this::notifyTeam)
            .doOnError(e -> rollbackProvisioning(request.getTenantId(), e));
    }
    
    private Mono<TenantProvisionResult> provisionDatabase(Tenant tenant) {
        switch (tenant.getTier()) {
            case FREE:
            case STANDARD:
                // Shared database - just create schema entries
                return createSharedSchemaEntries(tenant);
                
            case PREMIUM:
                // Dedicated schema in shared cluster
                return createDedicatedSchema(tenant);
                
            case ENTERPRISE:
                // Dedicated database instance
                return provisionDedicatedDatabase(tenant);
        }
    }
    
    private Mono<TenantProvisionResult> provisionInfrastructure(Tenant tenant) {
        if (tenant.getTier() == Tier.ENTERPRISE) {
            // Terraform/Pulumi to create dedicated resources
            return terraformService.apply(TerraformPlan.builder()
                .template("enterprise-tenant")
                .variable("tenant_id", tenant.getId())
                .variable("region", tenant.getRegion())
                .variable("cpu_limit", tenant.getResourceQuota().getCpu())
                .variable("memory_limit", tenant.getResourceQuota().getMemory())
                .build());
        }
        return Mono.just(TenantProvisionResult.shared(tenant));
    }
}

// Tenant Configuration Registry
@Service
public class TenantRegistry {
    private final ConcurrentHashMap<String, TenantConfig> configs = new ConcurrentHashMap<>();
    
    // Loaded from database, refreshed periodically or via events
    @PostConstruct
    public void loadConfigs() {
        tenantRepo.findAll().forEach(t -> configs.put(t.getId(), t.toConfig()));
    }
    
    @EventListener(TenantUpdatedEvent.class)
    public void onTenantUpdate(TenantUpdatedEvent event) {
        configs.put(event.getTenantId(), event.getConfig());
    }
    
    public TenantConfig getConfig(String tenantId) {
        TenantConfig config = configs.get(tenantId);
        if (config == null) {
            throw new TenantNotFoundException(tenantId);
        }
        return config;
    }
}

// Tier-based feature flags
public class TenantConfig {
    private String tenantId;
    private Tier tier;
    private int rateLimit;           // requests per second
    private int maxConnections;      // DB connection pool share
    private int maxStorage;          // GB
    private int maxUsers;
    private Set<Feature> features;   // Enabled features for this tier
    private String databaseUrl;      // Dedicated or shared
    private String region;
    private Map<String, String> customConfig;
}
```

---

## Problem 5: Data Migration Between Tenants

### Q9: How do you handle tenant data export, import, and migration?

```
SCENARIOS:
  1. Tenant wants to export their data (GDPR right to portability)
  2. Tenant upgrade: move from shared DB to dedicated DB
  3. Tenant offboarding: archive and delete data
  4. Merger: merge two tenants into one

EXPORT/IMPORT PIPELINE:

@Service
public class TenantDataService {
    
    // Export: Stream all tenant data to portable format
    public Flux<DataChunk> exportTenantData(String tenantId) {
        return Flux.concat(
            exportTable("users", tenantId),
            exportTable("orders", tenantId),
            exportTable("products", tenantId),
            exportTable("transactions", tenantId),
            exportAttachments(tenantId)
        )
        .map(data -> encrypt(data, tenantId)) // Encrypt export
        .buffer(1000)  // Batch into chunks
        .map(DataChunk::new);
    }
    
    // Migrate: Move tenant from shared to dedicated
    @Transactional
    public Mono<Void> migrateToDedicated(String tenantId) {
        return Mono.fromRunnable(() -> {
            // 1. Create dedicated database
            DatabaseInfo newDb = provisionDedicatedDb(tenantId);
            
            // 2. Copy data (while still serving from shared)
            copyDataToNewDb(tenantId, newDb);
            
            // 3. Set up CDC to capture changes during migration
            startChangeCapture(tenantId);
            
            // 4. Catch up CDC changes
            applyCapturedChanges(tenantId, newDb);
            
            // 5. Switch routing (atomic)
            tenantRegistry.updateDatabaseUrl(tenantId, newDb.getUrl());
            
            // 6. Verify (read from both, compare)
            verifyMigration(tenantId);
            
            // 7. Clean up old data from shared DB
            scheduleCleanup(tenantId, Duration.ofDays(7)); // Keep backup for 7 days
        });
    }
    
    // Offboard: GDPR-compliant data deletion
    public Mono<Void> offboardTenant(String tenantId) {
        return Mono.fromRunnable(() -> {
            // 1. Disable tenant (no new requests)
            tenantRegistry.disable(tenantId);
            
            // 2. Export final data backup (retain for legal hold period)
            exportToArchive(tenantId, Duration.ofDays(90));
            
            // 3. Delete all tenant data
            deleteAllTenantData(tenantId);
            
            // 4. Delete from caches
            cacheService.evictTenant(tenantId);
            
            // 5. Delete from search indexes
            searchService.deleteTenantIndex(tenantId);
            
            // 6. Revoke all access tokens
            authService.revokeAllTokens(tenantId);
            
            // 7. Remove tenant configuration
            tenantRegistry.remove(tenantId);
            
            // 8. Audit log
            auditService.log("TENANT_OFFBOARDED", tenantId);
        });
    }
}
```

---

## Problem 6: Platform Reliability and SRE

### Q10: How do you ensure platform reliability for all tenants?

```
PLATFORM SRE PRACTICES:

1. BLAST RADIUS REDUCTION:
   - Tenant isolation prevents one tenant from affecting others
   - Cell-based architecture (tenants grouped into cells)
   - Each cell is independent (own DB, own compute, own queue)
   - Cell failure affects only that cell's tenants
   
   Cell Architecture:
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │     Cell 1       │ │     Cell 2       │ │     Cell 3       │
   │ Tenants 1-100   │ │ Tenants 101-200  │ │ Tenants 201-300  │
   │ ┌─────┐ ┌─────┐│ │ ┌─────┐ ┌─────┐│ │ ┌─────┐ ┌─────┐│
   │ │ App │ │ DB  ││ │ │ App │ │ DB  ││ │ │ App │ │ DB  ││
   │ └─────┘ └─────┘│ │ └─────┘ └─────┘│ │ └─────┘ └─────┘│
   │ ┌─────┐ ┌─────┐│ │ ┌─────┐ ┌─────┐│ │ ┌─────┐ ┌─────┐│
   │ │Cache│ │Queue││ │ │Cache│ │Queue││ │ │Cache│ │Queue││
   │ └─────┘ └─────┘│ │ └─────┘ └─────┘│ │ └─────┘ └─────┘│
   └─────────────────┘ └─────────────────┘ └─────────────────┘

2. TENANT-AWARE CIRCUIT BREAKING:
   // If one tenant causes repeated failures, isolate them
   @Service
   public class TenantCircuitBreaker {
       private final Map<String, CircuitBreaker> breakers = new ConcurrentHashMap<>();
       
       public <T> Mono<T> execute(String tenantId, Supplier<Mono<T>> operation) {
           CircuitBreaker breaker = breakers.computeIfAbsent(tenantId, id ->
               CircuitBreaker.of(id, CircuitBreakerConfig.custom()
                   .failureRateThreshold(50)
                   .slidingWindowSize(20)
                   .waitDurationInOpenState(Duration.ofSeconds(30))
                   .build()));
           
           return Mono.fromCompletionStage(
               CircuitBreaker.decorateSupplier(breaker, () -> operation.get().toFuture()).get());
       }
   }

3. TENANT HEALTH SCORING:
   // Track per-tenant health metrics
   @Scheduled(fixedRate = 60000)
   public void computeTenantHealth() {
       for (TenantConfig tenant : tenantRegistry.getAll()) {
           double errorRate = metricsService.getErrorRate(tenant.getId(), Duration.ofMinutes(5));
           double latencyP99 = metricsService.getLatencyP99(tenant.getId());
           double resourceUsage = metricsService.getResourceUsage(tenant.getId());
           
           TenantHealthScore score = new TenantHealthScore(
               tenant.getId(), errorRate, latencyP99, resourceUsage);
           
           if (score.isUnhealthy()) {
               alertService.notifyTenantUnhealthy(tenant, score);
           }
           
           healthScoreRepo.save(score);
       }
   }

4. CAPACITY PLANNING PER TENANT:
   // Predict tenant growth and pre-allocate resources
   @Scheduled(cron = "0 0 2 * * MON") // Weekly
   public void capacityPlanning() {
       for (TenantConfig tenant : tenantRegistry.getPremiumTenants()) {
           UsageHistory history = usageService.getLast90Days(tenant.getId());
           UsageForecast forecast = forecastService.predict(history, Duration.ofDays(30));
           
           if (forecast.willExceedLimits()) {
               // Auto-scale or notify team
               if (tenant.isAutoScaleEnabled()) {
                   scalingService.scaleUp(tenant.getId(), forecast.getRecommendedResources());
               } else {
                   notifyAccountManager(tenant, forecast);
               }
           }
       }
   }
```
