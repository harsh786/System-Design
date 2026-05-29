# Performance Tuning - Complete Guide

## JVM Tuning

### Heap Sizing

```bash
# Traditional sizing
java -Xms2g -Xmx2g -jar app.jar

# Container-aware (JDK 10+)
java -XX:MaxRAMPercentage=75.0 \
     -XX:InitialRAMPercentage=75.0 \
     -XX:MinRAMPercentage=50.0 \
     -jar app.jar
```

**Rules of thumb:**
- Set `-Xms` = `-Xmx` to avoid heap resizing pauses
- In containers: use `MaxRAMPercentage=75.0` (leave 25% for metaspace, thread stacks, native memory, OS)
- For 4GB container: 75% = 3GB heap, leaving ~1GB for off-heap
- Never set heap > 75% of container memory (OOMKilled risk)

```dockerfile
# Dockerfile best practice
FROM eclipse-temurin:21-jre
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75.0 \
               -XX:InitialRAMPercentage=75.0 \
               -XX:+UseG1GC \
               -XX:+UseStringDeduplication"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app.jar"]
```

### GC Selection: G1GC vs ZGC vs Shenandoah vs Parallel

| GC | Pause Time | Throughput | Heap Overhead | Best For |
|---|---|---|---|---|
| **Parallel GC** | 100ms-1s+ | Highest (95%+) | Lowest | Batch jobs, data pipelines |
| **G1GC** | 10-200ms | High (90-95%) | ~10-15% | General purpose, balanced |
| **ZGC** | <1ms (typically ~0.1ms) | Good (85-92%) | ~15-20% | Low latency, large heaps |
| **Shenandoah** | <1ms | Good (85-90%) | ~15-20% | Low latency, OpenJDK |

**Selection criteria:**
```
if (batch_processing || throughput_critical):
    use Parallel GC (-XX:+UseParallelGC)
elif (heap > 16GB || p99_latency_SLA < 10ms):
    use ZGC (-XX:+UseZGC)
elif (heap > 4GB && balanced_needs):
    use G1GC (-XX:+UseG1GC)  # Default since JDK 9
elif (low_latency && openJDK):
    use Shenandoah (-XX:+UseShenandoahGC)
```

### G1GC Tuning Parameters

```bash
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \          # Target max pause (default 200ms)
     -XX:G1HeapRegionSize=16m \          # Region size (1-32MB, power of 2)
     -XX:InitiatingHeapOccupancyPercent=45 \ # Start concurrent marking (default 45%)
     -XX:G1ReservePercent=10 \           # Reserve for promotion failures
     -XX:G1MixedGCCountTarget=8 \        # Max mixed GC cycles
     -XX:G1MixedGCLiveThresholdPercent=85 \ # Skip regions with >85% live
     -XX:+UseStringDeduplication \       # Deduplicate String char arrays
     -XX:G1NewSizePercent=5 \            # Min young gen (default 5%)
     -XX:G1MaxNewSizePercent=60 \        # Max young gen (default 60%)
     -jar app.jar
```

**Key tuning decisions:**
- `MaxGCPauseMillis`: Lower = smaller young gen = more frequent GCs = lower throughput
- `G1HeapRegionSize`: Larger regions for large heaps (32GB+ use 32m). Formula: heap/2048
- `InitiatingHeapOccupancyPercent`: Lower = start marking earlier = less risk of full GC but more CPU
- If seeing "to-space exhausted" → increase `G1ReservePercent` or reduce allocation rate

### ZGC for Low Latency

```bash
# JDK 21+ Generational ZGC (recommended)
java -XX:+UseZGC -XX:+ZGenerational \
     -Xmx16g \
     -XX:SoftMaxHeapSize=12g \   # ZGC will try to stay below this
     -jar app.jar

# JDK 15-20 (non-generational)
java -XX:+UseZGC \
     -Xmx16g \
     -jar app.jar
```

**ZGC characteristics:**
- Pause times independent of heap size (tested with 16TB heaps)
- Concurrent relocation using colored pointers + load barriers
- Generational ZGC (JDK 21): 2-3x better throughput than non-generational
- No need to tune: `MaxGCPauseMillis` is irrelevant for ZGC
- Supports heap sizes from 8MB to 16TB

**When NOT to use ZGC:**
- Small heaps (<256MB) — overhead not justified
- Pure throughput workloads — Parallel GC wins by 5-10%
- Memory-constrained environments — ZGC needs ~15-20% more memory

### JIT Compilation Tiers

```
Tier 0: Interpreter (all methods start here)
Tier 1: C1 with full optimization (simple methods)
Tier 2: C1 with invocation & backedge counters
Tier 3: C1 with full profiling
Tier 4: C2 with full optimization (hot methods)
```

```bash
# Default: Tiered compilation (C1 + C2)
java -XX:+TieredCompilation -jar app.jar

# Disable C2 for faster startup (sacrifice peak performance)
java -XX:TieredStopAtLevel=1 -jar app.jar

# Increase code cache for large apps
java -XX:ReservedCodeCacheSize=512m \
     -XX:InitialCodeCacheSize=256m \
     -jar app.jar

# Print compilation decisions
java -XX:+PrintCompilation -jar app.jar

# Compilation thresholds
java -XX:CompileThreshold=10000 \      # Invocations before C2 compile
     -XX:Tier3InvocationThreshold=200 \ # Invocations before tier 3
     -XX:Tier4InvocationThreshold=5000 \
     -jar app.jar
```

**Warmup strategies for latency-sensitive apps:**
```java
@Component
public class WarmupRunner implements ApplicationRunner {
    @Override
    public void run(ApplicationArguments args) {
        // Force JIT compilation of hot paths
        for (int i = 0; i < 20_000; i++) {
            criticalBusinessMethod(syntheticInput);
        }
    }
}
```

### GC Logging and Analysis

```bash
# JDK 11+ unified logging
java -Xlog:gc*:file=gc.log:time,uptime,level,tags:filecount=5,filesize=50m \
     -Xlog:gc+heap=debug \
     -Xlog:gc+age=trace \
     -Xlog:safepoint \
     -jar app.jar

# Key metrics to extract from GC logs:
# - Pause time distribution (p50, p99, max)
# - Allocation rate (MB/s)
# - Promotion rate (MB/s) 
# - Concurrent marking duration
# - Mixed GC frequency
```

**Analysis tools:**
- GCViewer: Open source, visualizes pause times
- GCEasy (gceasy.io): Upload log, get analysis
- JClarity Censum: Commercial, detailed recommendations
- `jstat -gcutil <pid> 1000`: Real-time GC monitoring

```bash
# Real-time monitoring
jstat -gcutil $(pgrep -f app.jar) 1000
# S0  S1  E   O   M   CCS  YGC YGCT FGC FGCT GCT
# 0.0 98.2 45.1 67.3 95.2 92.1 124 2.341 3 0.892 3.233
```

### Native Memory Tracking (NMT)

```bash
# Enable NMT (5-10% performance overhead)
java -XX:NativeMemoryTracking=summary -jar app.jar

# Get memory report
jcmd <pid> VM.native_memory summary

# Baseline and diff
jcmd <pid> VM.native_memory baseline
# ... wait ...
jcmd <pid> VM.native_memory summary.diff
```

**Typical memory breakdown:**
```
Total: reserved=4567MB, committed=2345MB
- Java Heap:    reserved=2048MB, committed=2048MB
- Class:        reserved=1100MB, committed=120MB   (Metaspace)
- Thread:       reserved=256MB,  committed=256MB   (256 threads * 1MB stack)
- Code:         reserved=250MB,  committed=80MB    (JIT compiled code)
- GC:           reserved=200MB,  committed=150MB   (GC data structures)
- Internal:     reserved=50MB,   committed=50MB
- Direct:       reserved=128MB,  committed=64MB    (NIO direct buffers)
```

### Thread Stack Sizing

```bash
# Default: 1MB per thread (platform-dependent)
java -Xss512k -jar app.jar    # Reduce for many threads
java -Xss256k -jar app.jar    # Aggressive (watch for StackOverflowError)
```

**Calculation:**
- 200 threads × 1MB stack = 200MB native memory
- 200 threads × 512KB stack = 100MB (saved 100MB)
- Virtual threads use ~few KB each (JDK 21)

### Direct Memory for Netty

```bash
# Netty allocates direct ByteBuffers for I/O
java -XX:MaxDirectMemorySize=256m \   # Default = -Xmx value
     -Dio.netty.maxDirectMemory=256m \
     -Dio.netty.allocator.type=pooled \
     -Dio.netty.leakDetection.level=paranoid \ # Dev only
     -jar app.jar
```

**Sizing direct memory:**
- WebFlux app: `max_concurrent_connections × avg_buffer_size × 2`
- Example: 10,000 connections × 16KB × 2 = 320MB
- Monitor: `BufferPoolMXBean` for direct buffer usage

### Container-Aware JVM Flags (Complete)

```bash
java \
  # Memory
  -XX:MaxRAMPercentage=75.0 \
  -XX:InitialRAMPercentage=75.0 \
  -XX:+UseContainerSupport \           # Default ON since JDK 10
  -XX:MaxDirectMemorySize=256m \
  
  # GC
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=100 \
  
  # CPU (JVM auto-detects container CPU limits)
  -XX:ActiveProcessorCount=4 \         # Override if needed
  
  # Diagnostics
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/tmp/heapdump.hprof \
  -XX:+ExitOnOutOfMemoryError \        # Let orchestrator restart
  
  # JIT
  -XX:+TieredCompilation \
  -XX:ReservedCodeCacheSize=256m \
  
  -jar app.jar
```

---

## Spring Boot Startup Optimization

### Lazy Initialization

```yaml
# application.yml
spring:
  main:
    lazy-initialization: true  # All beans lazy by default
```

```java
// Exclude specific beans from lazy init
@Configuration
@Lazy(false)  // Eager initialization for this config
public class CriticalConfig {
    @Bean
    public CacheManager cacheManager() { ... }
}

// Per-bean lazy
@Service
@Lazy
public class ExpensiveService { ... }
```

**Tradeoffs:**
- Pro: 30-50% faster startup
- Con: First request latency spike, errors discovered late
- Recommendation: Use in dev/test, NOT production (unless you have warmup)

### Spring AOT Processing (Spring Boot 3)

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <executions>
        <execution>
            <id>process-aot</id>
            <goals>
                <goal>process-aot</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

**What AOT does:**
- Evaluates conditions at build time (eliminates runtime classpath scanning)
- Generates reflection-free bean factory code
- Pre-computes bean metadata
- Typical improvement: 20-40% faster startup

```bash
# Run with AOT-processed artifacts
java -Dspring.aot.enabled=true -jar app.jar
```

### GraalVM Native Image

```xml
<!-- pom.xml for native build -->
<plugin>
    <groupId>org.graalvm.buildtools</groupId>
    <artifactId>native-maven-plugin</artifactId>
</plugin>
```

```bash
# Build native image
mvn -Pnative native:compile

# Or with Spring Boot
mvn spring-boot:build-image -Pnative
```

**Tradeoffs:**

| Aspect | JVM | Native Image |
|--------|-----|-------------|
| Startup | 2-10s | 50-200ms |
| Memory at idle | 200-500MB | 50-100MB |
| Peak throughput | Higher (C2 JIT) | 10-30% lower |
| Build time | Seconds | 3-10 minutes |
| Debugging | Full | Limited |
| Reflection | Works | Requires config |
| Dynamic classloading | Works | Not supported |

**Best for:** Serverless, CLI tools, scale-to-zero microservices
**Avoid for:** Long-running services where peak throughput matters

### Class Data Sharing (CDS and AppCDS)

```bash
# Step 1: Create class list during training run
java -XX:DumpLoadedClassList=classes.lst \
     -jar app.jar --exit-after-startup

# Step 2: Create shared archive
java -Xshare:dump \
     -XX:SharedClassListFile=classes.lst \
     -XX:SharedArchiveFile=app-cds.jsa \
     -jar app.jar

# Step 3: Use archive at startup
java -Xshare:on \
     -XX:SharedArchiveFile=app-cds.jsa \
     -jar app.jar
```

**Impact:** 10-30% startup improvement, reduced memory footprint (shared pages between JVMs)

**Spring Boot 3.3+ auto-CDS:**
```bash
# Spring Boot now supports CDS out of the box
java -Dspring.context.exit=onRefresh -jar app.jar  # Training run
java -XX:ArchiveClassesAtExit=app.jsa -jar app.jar
java -XX:SharedArchiveFile=app.jsa -jar app.jar    # Fast start
```

### spring-context-indexer

```xml
<!-- pom.xml - generates META-INF/spring.components at compile time -->
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-context-indexer</artifactId>
    <optional>true</optional>
</dependency>
```

Eliminates classpath scanning at startup. Instead reads pre-computed index file.
Impact: Significant for large codebases (100+ components), negligible for small apps.

### Startup Endpoint Analysis

```yaml
# Enable startup tracking
management:
  endpoint:
    startup:
      enabled: true
  endpoints:
    web:
      exposure:
        include: startup

spring:
  application:
    startup: buffering  # Required to capture events
```

```java
@SpringBootApplication
public class App {
    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(App.class);
        app.setApplicationStartup(new BufferingApplicationStartup(2048));
        app.run(args);
    }
}
```

```bash
# Query startup events (sorted by duration)
curl localhost:8080/actuator/startup | jq '.timeline.events | sort_by(.duration) | reverse | .[0:10]'
```

### Reducing Auto-Configuration

```java
@SpringBootApplication(exclude = {
    DataSourceAutoConfiguration.class,
    HibernateJpaAutoConfiguration.class,
    MongoAutoConfiguration.class,
    SecurityAutoConfiguration.class,
    // Exclude what you don't need
})
public class App { }
```

```bash
# See all auto-configurations evaluated
java -jar app.jar --debug
# Look for: CONDITIONS EVALUATION REPORT
```

### Custom Condition Optimization

```java
// Avoid expensive conditions - use @ConditionalOnProperty over @ConditionalOnBean
// @ConditionalOnBean requires full bean creation, @ConditionalOnProperty is a simple check

@Configuration
@ConditionalOnProperty(name = "feature.x.enabled", havingValue = "true")
public class FeatureXConfig {
    // Only loaded when property is set
}
```

---

## Database Performance

### HikariCP Pool Sizing Formula

```
pool_size = (core_count * 2) + effective_spindle_count
```

**For SSDs (spindle_count ≈ 0):**
```
pool_size = core_count * 2
```

**Example:** 8-core server → pool_size = 16

**Why small pools work:** A database connection doing I/O doesn't hold a CPU core. But the DB itself is the bottleneck — more connections = more contention on locks, buffers, caches.

**Real-world guidance:**
- Start with `core_count * 2` (of the DATABASE server, not app server)
- PostgreSQL: Rarely need more than 20-30 connections per app instance
- With 10 microservices × 20 connections = 200 total (already a lot for most DBs)
- PgBouncer/ProxySQL for connection multiplexing at scale

### All HikariCP Properties

```yaml
spring:
  datasource:
    hikari:
      # Pool sizing
      maximum-pool-size: 16          # Max connections (default 10)
      minimum-idle: 16               # Keep pool fixed size (= max for production)
      
      # Timeouts
      connection-timeout: 30000      # Wait for connection from pool (ms), default 30s
      idle-timeout: 600000           # Retire idle connections (ms), default 10min
      max-lifetime: 1800000          # Max connection age (ms), default 30min
      keepalive-time: 300000         # Send keepalive query (ms), default 0 (disabled)
      validation-timeout: 5000       # Connection validation timeout (ms)
      
      # Connection testing
      connection-test-query: SELECT 1  # Only if JDBC4 isValid() not supported
      
      # Leak detection
      leak-detection-threshold: 60000  # Warn if connection held > 60s
      
      # Performance
      auto-commit: true              # Default true; set false for transaction-heavy
      pool-name: HikariPool-Main
      
      # Prepared statement cache (at driver level)
      data-source-properties:
        cachePrepStmts: true
        prepStmtCacheSize: 250
        prepStmtCacheSqlLimit: 2048
        useServerPrepStmts: true     # MySQL: use server-side prepared stmts
```

**Critical rules:**
1. Set `minimum-idle` = `maximum-pool-size` (fixed pool, no resize overhead)
2. Set `max-lifetime` < database's `wait_timeout` (MySQL default 8h, PG default unlimited)
3. Enable `leak-detection-threshold` in non-prod to catch connection leaks

### Hibernate Batch & Fetch Configuration

```yaml
spring:
  jpa:
    properties:
      hibernate:
        # Batching
        jdbc:
          batch_size: 50              # Batch INSERT/UPDATE statements
          batch_versioned_data: true  # Allow batching versioned entities
          fetch_size: 100             # JDBC fetch size (rows per roundtrip)
        order_inserts: true           # Order inserts for batching
        order_updates: true           # Order updates for batching
        
        # Query plan cache
        query:
          plan_cache_max_size: 2048   # Default 2048
          in_clause_parameter_padding: true  # Pad IN clauses to powers of 2
        
        # Statistics (dev/test only)
        generate_statistics: true
```

```java
// Batch insert example
@Transactional
public void batchInsert(List<Entity> entities) {
    for (int i = 0; i < entities.size(); i++) {
        entityManager.persist(entities.get(i));
        if (i % 50 == 0) {  // Match batch_size
            entityManager.flush();
            entityManager.clear();  // Prevent memory buildup
        }
    }
}
```

### N+1 Solutions

**Problem:**
```java
// Executes 1 query for orders + N queries for order items
List<Order> orders = orderRepo.findAll();
orders.forEach(o -> o.getItems().size());  // Triggers N lazy loads
```

**Solution 1: JOIN FETCH (JPQL)**
```java
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.status = :status")
List<Order> findWithItems(@Param("status") Status status);
// 1 query total
```

**Solution 2: @EntityGraph**
```java
@EntityGraph(attributePaths = {"items", "items.product"})
List<Order> findByStatus(Status status);
```

**Solution 3: @BatchSize (Hibernate)**
```java
@Entity
public class Order {
    @OneToMany(mappedBy = "order")
    @BatchSize(size = 50)  // Load items in batches of 50 orders
    private List<OrderItem> items;
}
// 1 query for orders + ceil(N/50) queries for items
```

**Solution 4: DTO Projection (best performance)**
```java
public interface OrderSummary {
    Long getId();
    String getCustomerName();
    BigDecimal getTotal();
}

@Query("SELECT o.id as id, o.customerName as customerName, " +
       "SUM(i.price) as total FROM Order o JOIN o.items i GROUP BY o.id, o.customerName")
List<OrderSummary> findOrderSummaries();
// 1 query, no entity mapping overhead
```

**Solution 5: Spring Data JPA @Query with Tuple**
```java
@Query(value = "SELECT o.*, i.* FROM orders o JOIN order_items i ON o.id = i.order_id",
       nativeQuery = true)
List<Object[]> findAllWithItemsNative();
```

### Read/Write Split Configuration

```yaml
# application.yml
spring:
  datasource:
    writer:
      url: jdbc:postgresql://primary:5432/mydb
      hikari:
        maximum-pool-size: 10
    reader:
      url: jdbc:postgresql://replica:5432/mydb
      hikari:
        maximum-pool-size: 20
```

```java
@Configuration
public class DataSourceConfig {
    
    @Bean
    @Primary
    public DataSource routingDataSource(
            @Qualifier("writerDataSource") DataSource writer,
            @Qualifier("readerDataSource") DataSource reader) {
        
        var routing = new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
                    ? "reader" : "writer";
            }
        };
        routing.setTargetDataSources(Map.of("writer", writer, "reader", reader));
        routing.setDefaultTargetDataSource(writer);
        return routing;
    }
}

// Usage
@Service
public class OrderService {
    @Transactional(readOnly = true)  // Routes to replica
    public List<Order> findOrders() { ... }
    
    @Transactional  // Routes to primary
    public Order createOrder(Order order) { ... }
}
```

### Query Plan Cache Tuning

```yaml
spring:
  jpa:
    properties:
      hibernate:
        query:
          plan_cache_max_size: 2048        # Default 2048, increase for many queries
          in_clause_parameter_padding: true # Reduces plan cache pollution
```

**IN clause padding example:**
- `WHERE id IN (?, ?, ?)` → padded to `WHERE id IN (?, ?, ?, ?)`  (power of 2)
- Without padding: IN(1), IN(1,2), IN(1,2,3)... = many different plans
- With padding: IN(1), IN(1,2), IN(1,2,3,4), IN(1,2,3,4,5,6,7,8)... = fewer plans

### Second-Level Cache (Ehcache/Redis)

```xml
<!-- Ehcache (local, fast) -->
<dependency>
    <groupId>org.hibernate.orm</groupId>
    <artifactId>hibernate-jcache</artifactId>
</dependency>
<dependency>
    <groupId>org.ehcache</groupId>
    <artifactId>ehcache</artifactId>
</dependency>
```

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          use_query_cache: true
          region:
            factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: org.ehcache.jsr107.EhcacheCachingProvider
```

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "products")
public class Product {
    @Id
    private Long id;
    private String name;
    // Mutable entity: READ_WRITE
}

@Entity
@Cache(usage = CacheConcurrencyStrategy.NONSTRICT_READ_WRITE, region = "categories")
@Immutable
public class Category {
    // Rarely changing: NONSTRICT_READ_WRITE
}
```

**Cache strategy selection:**
| Strategy | Consistency | Performance | Use Case |
|----------|------------|-------------|----------|
| READ_ONLY | Perfect | Highest | Immutable reference data |
| NONSTRICT_READ_WRITE | Eventual | High | Rarely updated |
| READ_WRITE | Strong (soft lock) | Medium | Frequently read, sometimes updated |
| TRANSACTIONAL | Full ACID | Lowest | JTA required |

### Statistics and Slow Query Detection

```yaml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
        session:
          events:
            log:
              LOG_QUERIES_SLOWER_THAN_MS: 100  # Log queries > 100ms

logging:
  level:
    org.hibernate.stat: DEBUG
    org.hibernate.SQL: DEBUG               # Log all SQL
    org.hibernate.type.descriptor.sql: TRACE  # Log bind parameters
```

```java
// Programmatic statistics access
@Component
@RequiredArgsConstructor
public class HibernateMetrics {
    private final EntityManagerFactory emf;
    
    @Scheduled(fixedRate = 60000)
    public void logStats() {
        Statistics stats = emf.unwrap(SessionFactoryImplementor.class).getStatistics();
        log.info("Queries executed: {}", stats.getQueryExecutionCount());
        log.info("Second-level cache hit ratio: {}", stats.getSecondLevelCacheHitCount() * 1.0 / 
            (stats.getSecondLevelCacheHitCount() + stats.getSecondLevelCacheMissCount()));
        log.info("Slowest query: {} ({}ms)", stats.getQueryExecutionMaxTimeQueryString(),
            stats.getQueryExecutionMaxTime());
    }
}
```

---

## HTTP & Network Performance

### Tomcat Thread Pool Configuration

```yaml
server:
  tomcat:
    threads:
      max: 200          # Max worker threads (default 200)
      min-spare: 25     # Min idle threads (default 10)
    max-connections: 8192  # Max connections (default 8192)
    accept-count: 100      # Queue when all connections busy (default 100)
    connection-timeout: 20000  # Connection timeout ms
    
    # For high-concurrency:
    # max-connections >> threads.max (connections can wait for thread)
    # accept-count = backlog queue for TCP when max-connections reached
```

**Sizing formula:**
```
threads.max = expected_concurrent_requests / (1 - blocking_ratio)

Example: 
- 100 concurrent requests, each spending 80% time waiting on DB/API
- threads.max = 100 / (1 - 0.8) = 500? NO — too many threads cause context switching
- Better: threads.max = 200, use async/reactive for I/O-heavy paths
```

**Thread pool sizing guidelines:**
- CPU-bound: threads = core_count + 1
- I/O-bound (traditional): threads = core_count × (1 + wait_time/compute_time)
- Practical max: 200-400 threads (beyond this, use WebFlux/virtual threads)

### Keep-Alive Tuning

```yaml
server:
  tomcat:
    keep-alive-timeout: 60000    # Keep-alive timeout (ms)
    max-keep-alive-requests: 100 # Max requests per connection
```

```yaml
# For reverse proxy (Nginx/ALB in front):
server:
  tomcat:
    keep-alive-timeout: 65000   # > proxy timeout (ALB default 60s)
```

### HTTP/2 Configuration

```yaml
server:
  http2:
    enabled: true     # Enable HTTP/2
  ssl:
    enabled: true     # HTTP/2 practically requires TLS
    key-store: classpath:keystore.p12
    key-store-password: changeit
    key-store-type: PKCS12
```

**HTTP/2 benefits:**
- Multiplexing: Multiple requests on single TCP connection
- Header compression (HPACK)
- Server push (though being deprecated in browsers)
- Binary framing (more efficient parsing)

**For h2c (HTTP/2 cleartext, behind reverse proxy):**
```yaml
server:
  http2:
    enabled: true
  # No SSL needed if behind TLS-terminating proxy
```

### Response Compression

```yaml
server:
  compression:
    enabled: true
    min-response-size: 1024        # Only compress > 1KB (default 2048)
    mime-types:
      - application/json
      - application/xml
      - text/html
      - text/xml
      - text/plain
      - application/javascript
      - text/css
```

**Note:** If behind Nginx/CloudFront that handles compression, disable in Spring Boot to avoid double-compression overhead.

### ETag and Conditional Requests

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Bean
    public FilterRegistrationBean<ShallowEtagHeaderFilter> shallowEtagFilter() {
        var reg = new FilterRegistrationBean<>(new ShallowEtagHeaderFilter());
        reg.addUrlPatterns("/api/*");
        reg.setOrder(1);
        return reg;
    }
}

// Or manual ETag control for performance
@GetMapping("/products/{id}")
public ResponseEntity<Product> getProduct(@PathVariable Long id, WebRequest request) {
    Product product = productService.findById(id);
    String etag = "\"" + product.getVersion() + "\"";
    
    if (request.checkNotModified(etag)) {
        return null;  // Returns 304 Not Modified
    }
    return ResponseEntity.ok().eTag(etag).body(product);
}
```

### WebClient Connection Pool (WebFlux)

```java
@Configuration
public class WebClientConfig {
    
    @Bean
    public WebClient webClient() {
        ConnectionProvider provider = ConnectionProvider.builder("custom")
            .maxConnections(500)                      // Max total connections
            .maxIdleTime(Duration.ofSeconds(20))      // Idle connection TTL
            .maxLifeTime(Duration.ofSeconds(60))      // Max connection age
            .pendingAcquireTimeout(Duration.ofSeconds(10))  // Wait for connection
            .pendingAcquireMaxCount(1000)             // Max pending requests
            .evictInBackground(Duration.ofSeconds(30)) // Background eviction
            .metrics(true)                            // Enable metrics
            .build();
        
        HttpClient httpClient = HttpClient.create(provider)
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
            .option(ChannelOption.SO_KEEPALIVE, true)
            .option(ChannelOption.TCP_NODELAY, true)
            .responseTimeout(Duration.ofSeconds(10))
            .doOnConnected(conn -> conn
                .addHandlerLast(new ReadTimeoutHandler(10))
                .addHandlerLast(new WriteTimeoutHandler(5)));
        
        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .codecs(config -> config.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
            .build();
    }
}
```

### DNS TTL Settings

```bash
# JVM DNS caching (networkaddress.cache.ttl)
# Default: 30s for positive, 10s for negative
java -Dsun.net.inetaddr.ttl=30 \
     -Dsun.net.inetaddr.negative.ttl=10 \
     -jar app.jar
```

```java
// Or programmatically
java.security.Security.setProperty("networkaddress.cache.ttl", "30");
java.security.Security.setProperty("networkaddress.cache.negative.ttl", "10");
```

**Important for cloud:** AWS ELBs change IPs; set TTL ≤ 60s. Default "forever" cache in JVM can cause connection failures after ELB scaling events.

### TCP Tuning

```java
// Netty channel options for WebFlux
@Bean
public NettyReactiveWebServerFactory nettyFactory() {
    NettyReactiveWebServerFactory factory = new NettyReactiveWebServerFactory();
    factory.addServerCustomizers(httpServer -> httpServer
        .option(ChannelOption.SO_BACKLOG, 1024)
        .childOption(ChannelOption.SO_KEEPALIVE, true)
        .childOption(ChannelOption.TCP_NODELAY, true)
        .childOption(ChannelOption.SO_RCVBUF, 65536)
        .childOption(ChannelOption.SO_SNDBUF, 65536)
    );
    return factory;
}
```

---

## Application-Level Performance

### Caching Strategy

**Local cache (Caffeine):**
```java
@Configuration
@EnableCaching
public class CacheConfig {
    
    @Bean
    public CacheManager caffeineCacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(5))
            .recordStats());  // Enable metrics
        return manager;
    }
}

@Service
public class ProductService {
    
    @Cacheable(value = "products", key = "#id")
    public Product findById(Long id) {
        return productRepo.findById(id).orElseThrow();
    }
    
    @CacheEvict(value = "products", key = "#product.id")
    public Product update(Product product) {
        return productRepo.save(product);
    }
    
    @CacheEvict(value = "products", allEntries = true)
    @Scheduled(fixedRate = 3600000)  // Hourly full eviction
    public void evictAll() {}
}
```

**Distributed cache (Redis):**
```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 300000     # 5 minutes
      cache-null-values: false
      use-key-prefix: true
      key-prefix: "myapp:"
  data:
    redis:
      host: redis-cluster
      port: 6379
      lettuce:
        pool:
          max-active: 16
          max-idle: 8
          min-idle: 4
```

**Multi-level cache (L1 local + L2 Redis):**
```java
@Component
public class MultiLevelCache {
    private final Cache<String, Object> l1 = Caffeine.newBuilder()
        .maximumSize(1000)
        .expireAfterWrite(Duration.ofMinutes(1))
        .build();
    
    private final RedisTemplate<String, Object> redis;
    
    public <T> T get(String key, Class<T> type, Supplier<T> loader) {
        // L1 check
        T value = type.cast(l1.getIfPresent(key));
        if (value != null) return value;
        
        // L2 check
        value = type.cast(redis.opsForValue().get(key));
        if (value != null) {
            l1.put(key, value);
            return value;
        }
        
        // Load from source
        value = loader.get();
        redis.opsForValue().set(key, value, Duration.ofMinutes(5));
        l1.put(key, value);
        return value;
    }
}
```

### Async Processing

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    
    @Bean("taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(8);
        executor.setMaxPoolSize(32);
        executor.setQueueCapacity(500);
        executor.setKeepAliveSeconds(60);
        executor.setThreadNamePrefix("async-");
        executor.setRejectedExecutionHandler(new CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }
}

@Service
public class OrderService {
    
    @Async("taskExecutor")
    public CompletableFuture<OrderReport> generateReport(Long orderId) {
        // Long-running task
        return CompletableFuture.completedFuture(report);
    }
    
    // Parallel fan-out
    public OrderDetails getOrderDetails(Long orderId) {
        CompletableFuture<Order> orderFuture = CompletableFuture.supplyAsync(
            () -> orderRepo.findById(orderId).orElseThrow(), executor);
        CompletableFuture<List<Payment>> paymentsFuture = CompletableFuture.supplyAsync(
            () -> paymentService.findByOrderId(orderId), executor);
        CompletableFuture<ShippingInfo> shippingFuture = CompletableFuture.supplyAsync(
            () -> shippingService.getInfo(orderId), executor);
        
        CompletableFuture.allOf(orderFuture, paymentsFuture, shippingFuture).join();
        
        return new OrderDetails(orderFuture.join(), paymentsFuture.join(), shippingFuture.join());
    }
}
```

### Pagination: Offset vs Cursor/Keyset

**Offset pagination (simple but slow for deep pages):**
```java
// Page 1000 of results: DB must skip 999,000 rows!
@GetMapping("/orders")
public Page<Order> getOrders(@RequestParam int page, @RequestParam int size) {
    return orderRepo.findAll(PageRequest.of(page, size, Sort.by("createdAt").descending()));
}
// SQL: SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 999980
// Performance: O(offset + limit) — gets slower as page increases
```

**Cursor/Keyset pagination (constant time regardless of page):**
```java
@GetMapping("/orders")
public CursorPage<Order> getOrders(
        @RequestParam(required = false) Instant cursor,
        @RequestParam(defaultValue = "20") int limit) {
    
    List<Order> orders;
    if (cursor == null) {
        orders = orderRepo.findTopN(limit + 1);  // +1 to detect hasMore
    } else {
        orders = orderRepo.findAfterCursor(cursor, limit + 1);
    }
    
    boolean hasMore = orders.size() > limit;
    if (hasMore) orders = orders.subList(0, limit);
    
    Instant nextCursor = hasMore ? orders.get(orders.size() - 1).getCreatedAt() : null;
    return new CursorPage<>(orders, nextCursor, hasMore);
}

@Query("SELECT o FROM Order o WHERE o.createdAt < :cursor ORDER BY o.createdAt DESC LIMIT :limit")
List<Order> findAfterCursor(@Param("cursor") Instant cursor, @Param("limit") int limit);
// SQL: SELECT * FROM orders WHERE created_at < '2024-01-15' ORDER BY created_at DESC LIMIT 21
// Performance: O(limit) — uses index, constant time
```

**When to use each:**
- Offset: Admin panels, total count needed, small datasets
- Cursor: Infinite scroll, APIs, large datasets, real-time feeds

### Jackson Serialization Optimization

```xml
<!-- Afterburner module (bytecode generation, 20-30% faster) -->
<dependency>
    <groupId>com.fasterxml.jackson.module</groupId>
    <artifactId>jackson-module-afterburner</artifactId>
</dependency>
<!-- Or Blackbird for JDK 11+ (uses MethodHandles, even faster) -->
<dependency>
    <groupId>com.fasterxml.jackson.module</groupId>
    <artifactId>jackson-module-blackbird</artifactId>
</dependency>
```

```java
@Configuration
public class JacksonConfig {
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer customizer() {
        return builder -> builder
            .modulesToInstall(new BlackbirdModule())  // Or AfterburnerModule
            .featuresToDisable(
                SerializationFeature.WRITE_DATES_AS_TIMESTAMPS,
                DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES
            )
            .featuresToEnable(
                DeserializationFeature.USE_LONG_FOR_INTS  // Avoid BigDecimal for JSON ints
            );
    }
}

// Custom serializer for hot paths
public class MoneySerializer extends JsonSerializer<BigDecimal> {
    @Override
    public void serialize(BigDecimal value, JsonGenerator gen, SerializerProvider sp) throws IOException {
        gen.writeString(value.setScale(2, RoundingMode.HALF_UP).toPlainString());
    }
}
```

### Object Pooling

```java
// Apache Commons Pool for expensive-to-create objects
@Configuration
public class PoolConfig {
    
    @Bean
    public GenericObjectPool<ExpensiveClient> clientPool() {
        GenericObjectPoolConfig<ExpensiveClient> config = new GenericObjectPoolConfig<>();
        config.setMaxTotal(20);
        config.setMaxIdle(10);
        config.setMinIdle(5);
        config.setTestOnBorrow(true);
        config.setMaxWait(Duration.ofSeconds(5));
        
        return new GenericObjectPool<>(new BasePooledObjectFactory<>() {
            @Override
            public ExpensiveClient create() { return new ExpensiveClient(); }
            
            @Override
            public PooledObject<ExpensiveClient> wrap(ExpensiveClient obj) {
                return new DefaultPooledObject<>(obj);
            }
            
            @Override
            public boolean validateObject(PooledObject<ExpensiveClient> p) {
                return p.getObject().isConnected();
            }
        }, config);
    }
}

// Usage
public void doWork() {
    ExpensiveClient client = pool.borrowObject();
    try {
        client.execute();
    } finally {
        pool.returnObject(client);
    }
}
```

### Virtual Threads (JDK 21)

```yaml
# Spring Boot 3.2+
spring:
  threads:
    virtual:
      enabled: true  # Tomcat uses virtual threads for request handling
```

```java
// Or configure manually
@Bean
public TomcatProtocolHandlerCustomizer<?> virtualThreadCustomizer() {
    return handler -> handler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
}

// Virtual thread executor for async tasks
@Bean("virtualExecutor")
public Executor virtualThreadExecutor() {
    return Executors.newVirtualThreadPerTaskExecutor();
}
```

**Virtual threads vs Reactive:**

| Aspect | Virtual Threads | Reactive (WebFlux) |
|--------|----------------|-------------------|
| Programming model | Imperative (familiar) | Functional (Mono/Flux) |
| Learning curve | Low | High |
| Debugging | Normal stack traces | Complex |
| Library support | All blocking libs work | Need reactive drivers |
| Scalability | Very high (millions of threads) | Very high (event loop) |
| CPU-bound work | No benefit | No benefit |
| Best for | Brownfield apps, simple I/O | Streaming, backpressure needed |

**When to use virtual threads:**
- Existing blocking code (JDBC, RestTemplate, etc.)
- Simple request/response patterns
- Team unfamiliar with reactive

**When to stay reactive:**
- Streaming responses
- Need backpressure
- Already using WebFlux successfully

### Batch Operations

```java
// JdbcTemplate batch
@Repository
public class OrderBatchRepo {
    
    public void batchInsert(List<Order> orders) {
        jdbcTemplate.batchUpdate(
            "INSERT INTO orders (id, customer_id, total, status) VALUES (?, ?, ?, ?)",
            new BatchPreparedStatementSetter() {
                @Override
                public void setValues(PreparedStatement ps, int i) throws SQLException {
                    Order o = orders.get(i);
                    ps.setLong(1, o.getId());
                    ps.setLong(2, o.getCustomerId());
                    ps.setBigDecimal(3, o.getTotal());
                    ps.setString(4, o.getStatus().name());
                }
                @Override
                public int getBatchSize() { return orders.size(); }
            }
        );
    }
}

// Spring Batch for large-scale ETL
@Bean
public Step processStep(JobRepository jobRepo, PlatformTransactionManager txManager) {
    return new StepBuilder("processStep", jobRepo)
        .<InputRecord, OutputRecord>chunk(1000, txManager)  // Process 1000 records per chunk
        .reader(reader())
        .processor(processor())
        .writer(writer())
        .faultTolerant()
        .retryLimit(3)
        .retry(TransientDataAccessException.class)
        .build();
}
```

---

## Monitoring & Benchmarking

### RED Method (Rate, Errors, Duration)

For every service, monitor:
- **Rate:** Requests per second
- **Errors:** Failed requests per second
- **Duration:** Distribution of request latency

```java
// Spring Boot auto-exposes these via Micrometer
// http.server.requests timer = rate + duration
// http.server.requests with tag outcome=SERVER_ERROR = errors

// Custom RED metrics
@Component
@RequiredArgsConstructor
public class OrderMetrics {
    private final MeterRegistry registry;
    
    public void recordOrder(String type, boolean success, Duration duration) {
        Timer.builder("orders.processed")
            .tag("type", type)
            .tag("success", String.valueOf(success))
            .register(registry)
            .record(duration);
        
        if (!success) {
            registry.counter("orders.errors", "type", type).increment();
        }
    }
}
```

### USE Method (Utilization, Saturation, Errors)

For every resource (CPU, memory, disk, network, thread pool, connection pool):
- **Utilization:** % time resource is busy
- **Saturation:** Queue depth / backlog
- **Errors:** Error events on the resource

```java
// Thread pool monitoring
@Bean
public ExecutorService monitoredExecutor(MeterRegistry registry) {
    ExecutorService executor = Executors.newFixedThreadPool(16);
    return ExecutorServiceMetrics.monitor(registry, executor, "business-executor");
    // Exposes: executor.pool.size, executor.active, executor.queued, executor.completed
}

// HikariCP auto-monitored by Spring Boot:
// hikaricp.connections.active (utilization)
// hikaricp.connections.pending (saturation)
// hikaricp.connections.timeout (errors)
```

### Key Micrometer Metrics to Monitor

```yaml
management:
  metrics:
    enable:
      all: true
    distribution:
      percentiles-histogram:
        http.server.requests: true
      slo:
        http.server.requests: 50ms, 100ms, 200ms, 500ms, 1s
      percentiles:
        http.server.requests: 0.5, 0.95, 0.99
```

**Critical metrics dashboard:**
```
# JVM
jvm.memory.used{area="heap"}
jvm.memory.used{area="nonheap"}
jvm.gc.pause{action="end of major GC"}
jvm.threads.live
jvm.threads.states{state="blocked"}

# HTTP
http.server.requests (rate, p50, p95, p99)
http.server.requests{outcome="SERVER_ERROR"} (error rate)

# Connection Pool
hikaricp.connections.active
hikaricp.connections.pending
hikaricp.connections.usage (timer: how long connections are held)

# Business
orders.created.count
payments.processed.duration

# System
system.cpu.usage
process.cpu.usage
disk.total / disk.free
```

### JMH Microbenchmarking

```java
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@State(Scope.Benchmark)
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 10, time = 1)
@Fork(2)
public class SerializationBenchmark {
    
    private ObjectMapper objectMapper;
    private ObjectMapper afterburnerMapper;
    private Order testOrder;
    
    @Setup
    public void setup() {
        objectMapper = new ObjectMapper();
        afterburnerMapper = new ObjectMapper();
        afterburnerMapper.registerModule(new AfterburnerModule());
        testOrder = createLargeOrder();
    }
    
    @Benchmark
    public byte[] baseline_jackson() throws Exception {
        return objectMapper.writeValueAsBytes(testOrder);
    }
    
    @Benchmark
    public byte[] optimized_afterburner() throws Exception {
        return afterburnerMapper.writeValueAsBytes(testOrder);
    }
    
    @Benchmark
    public byte[] manual_streaming() throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream(4096);
        try (JsonGenerator gen = objectMapper.getFactory().createGenerator(out)) {
            gen.writeStartObject();
            gen.writeNumberField("id", testOrder.getId());
            gen.writeStringField("status", testOrder.getStatus().name());
            gen.writeEndObject();
        }
        return out.toByteArray();
    }
}
```

```bash
# Run benchmarks
mvn clean package -pl benchmarks
java -jar benchmarks/target/benchmarks.jar -rf json -rff results.json
```

**Sample results:**
```
Benchmark                          Mode  Cnt    Score   Error   Units
baseline_jackson                  thrpt   20   245.3 ± 12.1   ops/ms
optimized_afterburner             thrpt   20   312.7 ± 8.4    ops/ms  (+27%)
manual_streaming                  thrpt   20   489.2 ± 15.6   ops/ms  (+99%)
```

### Load Testing with Gatling/k6

**k6 script:**
```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const orderDuration = new Trend('order_duration');

export const options = {
    stages: [
        { duration: '2m', target: 100 },   // Ramp up
        { duration: '5m', target: 100 },   // Sustain
        { duration: '2m', target: 500 },   // Stress
        { duration: '5m', target: 500 },   // Sustain stress
        { duration: '2m', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<200', 'p(99)<500'],
        errors: ['rate<0.01'],  // <1% error rate
    },
};

export default function () {
    const res = http.get('http://localhost:8080/api/orders?page=0&size=20');
    
    check(res, {
        'status is 200': (r) => r.status === 200,
        'response time < 200ms': (r) => r.timings.duration < 200,
    });
    
    errorRate.add(res.status >= 400);
    orderDuration.add(res.timings.duration);
    
    sleep(1);
}
```

```bash
# Run load test
k6 run load-test.js

# With Prometheus output
k6 run --out experimental-prometheus-rw load-test.js
```

**Gatling (Scala DSL):**
```scala
class OrderSimulation extends Simulation {
    val httpProtocol = http.baseUrl("http://localhost:8080")
        .acceptHeader("application/json")
    
    val scn = scenario("Order Flow")
        .exec(http("List Orders").get("/api/orders"))
        .pause(1)
        .exec(http("Create Order")
            .post("/api/orders")
            .body(StringBody("""{"customerId": 1, "items": [{"productId": 1, "qty": 2}]}"""))
            .check(jsonPath("$.id").saveAs("orderId")))
        .pause(1)
        .exec(http("Get Order").get("/api/orders/${orderId}"))
    
    setUp(
        scn.inject(
            rampUsersPerSec(1).to(100).during(120),
            constantUsersPerSec(100).during(300)
        )
    ).protocols(httpProtocol)
     .assertions(
         global.responseTime.percentile3.lt(500),  // p95 < 500ms
         global.successfulRequests.percent.gt(99)
     )
}
```

### Flame Graph Interpretation

```bash
# Generate flame graph with async-profiler
./asprof -d 30 -f flamegraph.html <pid>

# CPU profiling
./asprof -e cpu -d 60 -f cpu-flame.html <pid>

# Allocation profiling (find GC pressure sources)
./asprof -e alloc -d 60 -f alloc-flame.html <pid>

# Wall-clock profiling (includes I/O wait)
./asprof -e wall -t -d 60 -f wall-flame.html <pid>

# Lock contention
./asprof -e lock -d 60 -f lock-flame.html <pid>
```

**Reading flame graphs:**
- X-axis: Percentage of samples (NOT time progression)
- Y-axis: Stack depth (bottom = entry point, top = leaf function)
- Width: Proportional to time spent in that frame
- Look for: Wide plateaus at the top (CPU hotspots)
- Color: Usually random, but can indicate Java/native/kernel

**Common patterns:**
- Wide `GC` frames → memory pressure
- Wide `ThreadPoolExecutor.getTask` → threads idle (good or overprovisioned)
- Wide `SocketRead` → waiting on network (expected for I/O)
- Wide `Lock.park` → contention

### Java Flight Recorder (JFR)

```bash
# Start recording
jcmd <pid> JFR.start name=perf duration=60s filename=recording.jfr \
    settings=profile

# Or at startup
java -XX:StartFlightRecording=duration=60s,filename=recording.jfr \
     -jar app.jar

# Continuous recording (circular buffer)
java -XX:StartFlightRecording=disk=true,maxsize=500m,maxage=1h \
     -jar app.jar

# Dump on demand
jcmd <pid> JFR.dump name=1 filename=dump.jfr
```

**Key JFR events to monitor:**
- `jdk.GCPhasePause` — GC pause durations
- `jdk.CPULoad` — process and machine CPU
- `jdk.ThreadPark` — thread blocking
- `jdk.SocketRead` / `jdk.SocketWrite` — network I/O latency
- `jdk.FileRead` / `jdk.FileWrite` — disk I/O
- `jdk.ObjectAllocationOutsideTLAB` — expensive allocations
- `jdk.JavaMonitorEnter` — lock contention

### Production Profiling Best Practices

1. **Always-on, low-overhead recording:**
   ```bash
   java -XX:StartFlightRecording=disk=true,maxsize=200m,maxage=6h,settings=default \
        -jar app.jar
   # 'default' profile: <1% overhead
   # 'profile' setting: ~2% overhead (more detail)
   ```

2. **On-demand async-profiler (near-zero overhead when idle):**
   ```bash
   # Attach to running process, sample for 30s
   ./asprof -d 30 -f /tmp/flame.html <pid>
   ```

3. **Continuous profiling services:**
   - Pyroscope (open source)
   - Datadog Continuous Profiler
   - AWS CodeGuru Profiler
   - Google Cloud Profiler

4. **Rules:**
   - Never use `-Xprof` or HPROF in production
   - JFR with `default` settings is production-safe
   - async-profiler is production-safe (uses perf_events)
   - Avoid heap dumps in production unless necessary (stops the world)
   - Use sampling profilers, never instrumenting profilers in prod

---

## Performance Tuning Checklist for Interviews

### Quick Reference: Top 10 Performance Wins

| # | Optimization | Typical Impact | Effort |
|---|---|---|---|
| 1 | Fix N+1 queries | 10-100x for affected endpoints | Low |
| 2 | Add caching (Caffeine/Redis) | 5-50x for cached data | Low |
| 3 | Right-size connection pool | 2-5x throughput | Low |
| 4 | Enable HTTP/2 + compression | 20-50% latency reduction | Low |
| 5 | Cursor pagination | 100x+ for deep pages | Medium |
| 6 | Batch database operations | 5-20x for bulk writes | Medium |
| 7 | Tune GC (G1→ZGC for latency) | 10-100x p99 improvement | Medium |
| 8 | Virtual threads or reactive | 5-10x concurrent capacity | High |
| 9 | GraalVM native image | 10-50x startup | High |
| 10 | Read replicas + connection routing | 2-3x read throughput | High |

### Interview Talking Points

**"How do you approach performance tuning?"**
1. **Measure first** — never optimize without data
2. **Identify bottleneck** — USE/RED methods, profiling
3. **Optimize the bottleneck** — not everything else
4. **Verify improvement** — A/B test or load test
5. **Monitor regression** — alerts on SLOs

**"How do you size a JVM for containers?"**
- MaxRAMPercentage=75% of container memory
- Account for: heap + metaspace + thread stacks + direct buffers + native code
- Formula: container_memory = heap + (threads × stack_size) + metaspace + direct_memory + OS_overhead
- Example: 4GB container → 3GB heap, 200 threads × 512KB = 100MB, ~200MB metaspace, 256MB direct = ~3.5GB total

**"When would you choose reactive over virtual threads?"**
- Reactive: streaming, backpressure, already reactive stack, complex async composition
- Virtual threads: brownfield, blocking I/O libraries, simpler mental model, JDBC-heavy
- Both: massive concurrency (10K+ simultaneous I/O operations)
- Neither: CPU-bound (use parallel streams / ForkJoinPool)
