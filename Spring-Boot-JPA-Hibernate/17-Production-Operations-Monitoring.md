# Production Operations & Monitoring (Staff Engineer / Architect Level)

## 1. Hibernate Statistics & Metrics

### Enabling Hibernate Statistics

```yaml
# application.yml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
        session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 25
```

```java
@Configuration
public class HibernateStatsConfig {

    @Bean
    public StatisticsService statisticsService(EntityManagerFactory emf) {
        SessionFactory sessionFactory = emf.unwrap(SessionFactory.class);
        Statistics statistics = sessionFactory.getStatistics();
        statistics.setStatisticsEnabled(true);
        return new StatisticsService(statistics);
    }
}
```

### Micrometer Integration for Hibernate Metrics

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```java
@Configuration
public class HibernateMetricsConfig {

    @Bean
    public HibernateMetrics hibernateMetrics(EntityManagerFactory emf) {
        return new HibernateMetrics(
            emf.unwrap(SessionFactory.class),
            "persistence-unit",
            Tags.empty()
        );
    }

    // Custom metrics beyond what Micrometer provides OOTB
    @Bean
    public MeterBinder hibernateDetailedMetrics(EntityManagerFactory emf) {
        return registry -> {
            Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();

            Gauge.builder("hibernate.sessions.open", stats, Statistics::getSessionOpenCount)
                .description("Total sessions opened")
                .register(registry);

            Gauge.builder("hibernate.sessions.closed", stats, Statistics::getSessionCloseCount)
                .description("Total sessions closed")
                .register(registry);

            Gauge.builder("hibernate.transactions.success", stats, Statistics::getSuccessfulTransactionCount)
                .register(registry);

            Gauge.builder("hibernate.transactions.failure", stats, s ->
                s.getTransactionCount() - s.getSuccessfulTransactionCount())
                .register(registry);

            Gauge.builder("hibernate.cache.second_level.hit", stats, Statistics::getSecondLevelCacheHitCount)
                .register(registry);

            Gauge.builder("hibernate.cache.second_level.miss", stats, Statistics::getSecondLevelCacheMissCount)
                .register(registry);

            Gauge.builder("hibernate.cache.second_level.put", stats, Statistics::getSecondLevelCachePutCount)
                .register(registry);

            Gauge.builder("hibernate.cache.query.hit", stats, Statistics::getQueryCacheHitCount)
                .register(registry);

            Gauge.builder("hibernate.cache.query.miss", stats, Statistics::getQueryCacheMissCount)
                .register(registry);

            Gauge.builder("hibernate.entities.load", stats, Statistics::getEntityLoadCount)
                .register(registry);

            Gauge.builder("hibernate.entities.insert", stats, Statistics::getEntityInsertCount)
                .register(registry);

            Gauge.builder("hibernate.entities.update", stats, Statistics::getEntityUpdateCount)
                .register(registry);

            Gauge.builder("hibernate.entities.delete", stats, Statistics::getEntityDeleteCount)
                .register(registry);

            Gauge.builder("hibernate.entities.fetch", stats, Statistics::getEntityFetchCount)
                .register(registry);

            Gauge.builder("hibernate.collections.load", stats, Statistics::getCollectionLoadCount)
                .register(registry);

            Gauge.builder("hibernate.collections.fetch", stats, Statistics::getCollectionFetchCount)
                .register(registry);

            Gauge.builder("hibernate.queries.executed", stats, Statistics::getQueryExecutionCount)
                .register(registry);

            Gauge.builder("hibernate.queries.max_time", stats, Statistics::getQueryExecutionMaxTime)
                .register(registry);

            Gauge.builder("hibernate.flushes", stats, Statistics::getFlushCount)
                .register(registry);

            Gauge.builder("hibernate.optimistic_lock_failures", stats, Statistics::getOptimisticFailureCount)
                .register(registry);
        };
    }
}
```

### Per-Request Query Counting (Critical for N+1 Detection)

```java
@Component
@RequestScope
public class QueryCounter {

    private final AtomicInteger queryCount = new AtomicInteger(0);
    private final List<String> queries = new CopyOnWriteArrayList<>();

    public void increment(String sql) {
        queryCount.incrementAndGet();
        queries.add(sql);
    }

    public int getCount() {
        return queryCount.get();
    }

    public List<String> getQueries() {
        return Collections.unmodifiableList(queries);
    }
}

@Component
public class QueryCountStatementInspector implements StatementInspector {

    @Override
    public String inspect(String sql) {
        try {
            QueryCounter counter = ApplicationContextProvider
                .getBean(QueryCounter.class);
            counter.increment(sql);
        } catch (Exception ignored) {
            // Outside request scope
        }
        return sql;
    }
}

// Register in properties
// spring.jpa.properties.hibernate.session_factory.statement_inspector=
//   com.example.QueryCountStatementInspector
```

### Grafana Dashboard Panel Descriptions

| Panel | Query (PromQL) | Purpose |
|-------|---------------|---------|
| Query Rate | `rate(hibernate_queries_executed_total[5m])` | Queries/sec trend |
| Entity Loads | `rate(hibernate_entities_load_total[5m])` | Entity loading pressure |
| L2 Cache Hit Ratio | `hibernate_cache_second_level_hit / (hibernate_cache_second_level_hit + hibernate_cache_second_level_miss)` | Cache effectiveness |
| Session Count | `hibernate_sessions_open - hibernate_sessions_closed` | Leaked sessions |
| Flush Count | `rate(hibernate_flushes_total[5m])` | Dirty checking pressure |
| Optimistic Lock Failures | `rate(hibernate_optimistic_lock_failures_total[5m])` | Contention indicator |
| Queries per Request | `histogram_quantile(0.95, request_query_count_bucket)` | N+1 detection |
| Slow Queries | `rate(hibernate_queries_max_time[5m])` | Performance degradation |

### Alerting Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: hibernate_alerts
    rules:
      - alert: HighQueryCountPerRequest
        expr: histogram_quantile(0.95, rate(request_query_count_bucket[5m])) > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High query count per request (p95 > 20)"
          description: "Likely N+1 problem. p95 query count: {{ $value }}"

      - alert: ExcessiveEntityLoading
        expr: rate(hibernate_entities_load_total[5m]) / rate(http_server_requests_seconds_count[5m]) > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Excessive entity loading per request (> 500)"

      - alert: LowCacheHitRatio
        expr: >
          hibernate_cache_second_level_hit /
          (hibernate_cache_second_level_hit + hibernate_cache_second_level_miss) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "L2 cache hit ratio below 70%"
          description: "Current ratio: {{ $value | humanizePercentage }}"

      - alert: HighOptimisticLockFailureRate
        expr: rate(hibernate_optimistic_lock_failures_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High optimistic lock failure rate (> 10/sec)"

      - alert: SessionLeak
        expr: (hibernate_sessions_open - hibernate_sessions_closed) > 50
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Possible Hibernate session leak"
```

---

## 2. SQL Logging & Analysis

### Development: Full SQL Logging

```yaml
# application-dev.yml
logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.orm.jdbc.bind: TRACE  # Hibernate 6+
    # Hibernate 5: org.hibernate.type.descriptor.sql.BasicBinder: TRACE

spring:
  jpa:
    properties:
      hibernate:
        format_sql: true
        use_sql_comments: true  # Shows JPQL/HQL origin
```

### Production: datasource-proxy

```xml
<dependency>
    <groupId>net.ttddyy</groupId>
    <artifactId>datasource-proxy</artifactId>
    <version>1.9</version>
</dependency>
```

```java
@Configuration
public class DataSourceProxyConfig {

    @Bean
    public BeanPostProcessor dataSourceProxyBeanPostProcessor() {
        return new BeanPostProcessor() {
            @Override
            public Object postProcessAfterInitialization(Object bean, String beanName) {
                if (bean instanceof DataSource && !(bean instanceof ProxyDataSource)) {
                    return ProxyDataSourceBuilder.create((DataSource) bean)
                        .name("application-ds")
                        .multiline()
                        .listener(new SlowQueryListener() {{
                            setThreshold(500); // ms
                            addListener((execInfo, queryInfoList) -> {
                                log.warn("Slow query detected ({}ms): {}",
                                    execInfo.getElapsedTime(),
                                    queryInfoList.get(0).getQuery());
                            });
                        }})
                        .listener(new QueryCountStrategy())
                        .countQuery()
                        .logQueryBySlf4j(SLF4JLogLevel.INFO,
                            "datasource-proxy-query-logger")
                        .build();
                }
                return bean;
            }
        };
    }
}
```

### Production: Hibernate Slow Query Log (6.x+)

```yaml
spring:
  jpa:
    properties:
      hibernate:
        session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 100
```

This logs via `org.hibernate.SQL_SLOW` logger at INFO level.

### Production: p6spy Configuration

```properties
# spy.properties
driverlist=org.postgresql.Driver
autoflush=true
appender=com.p6spy.engine.spy.appender.Slf4JLogger
logMessageFormat=com.p6spy.engine.spy.appender.CustomLineFormat
customLogMessageFormat=%(executionTime)ms | %(sqlSingleLine)
excludecategories=info,debug,result,resultset,batch
filter=true
executionThreshold=100
```

### Database-Level Slow Query Log (PostgreSQL)

```sql
-- postgresql.conf
log_min_duration_statement = 200   -- Log queries > 200ms
log_statement = 'none'             -- Don't double-log
log_line_prefix = '%t [%p] %u@%d '
auto_explain.log_min_duration = 500  -- Log execution plans for queries > 500ms
auto_explain.log_analyze = true
auto_explain.log_buffers = true

-- Enable auto_explain extension
shared_preload_libraries = 'auto_explain'
```

### Correlating SQL with Business Operations (MDC)

```java
@Component
public class TraceIdFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String traceId = Optional.ofNullable(request.getHeader("X-Trace-Id"))
            .orElse(UUID.randomUUID().toString().substring(0, 8));

        MDC.put("traceId", traceId);
        MDC.put("requestUri", request.getRequestURI());
        MDC.put("userId", extractUserId(request));

        try {
            chain.doFilter(request, response);
        } finally {
            MDC.clear();
        }
    }
}

// Hibernate comment injection for SQL correlation
@Configuration
public class HibernateCommentConfig {

    @Bean
    public HibernatePropertiesCustomizer hibernatePropertiesCustomizer() {
        return props -> {
            props.put("hibernate.use_sql_comments", "true");
            props.put("hibernate.session_factory.statement_inspector",
                new CorrelatingStatementInspector());
        };
    }
}

public class CorrelatingStatementInspector implements StatementInspector {

    @Override
    public String inspect(String sql) {
        String traceId = MDC.get("traceId");
        if (traceId != null) {
            return "/* traceId=" + traceId + " */ " + sql;
        }
        return sql;
    }
}
```

### Structured SQL Log Format for Analysis

```java
@Slf4j
public class StructuredQueryLogger implements QueryExecutionListener {

    @Override
    public void afterQuery(ExecutionInfo execInfo, List<QueryInfo> queryInfoList) {
        for (QueryInfo qi : queryInfoList) {
            log.info("sql_execution traceId={} duration_ms={} query={} params={}",
                MDC.get("traceId"),
                execInfo.getElapsedTime(),
                qi.getQuery().replaceAll("\\s+", " ").trim(),
                qi.getParametersList()
            );
        }
    }

    @Override
    public void beforeQuery(ExecutionInfo execInfo, List<QueryInfo> queryInfoList) {}
}
```

---

## 3. Connection Pool Monitoring & Tuning

### HikariCP Complete Configuration

```yaml
spring:
  datasource:
    hikari:
      # === Pool Sizing ===
      maximum-pool-size: 10          # Max connections. Formula: (cores * 2) + spindles
      minimum-idle: 10               # Keep equal to max for fixed-size pool (recommended)

      # === Timeouts ===
      connection-timeout: 30000      # Max wait for connection from pool (ms). Default: 30s
      idle-timeout: 600000           # Max idle time before eviction (ms). Default: 10min
                                     # Only applies when minimumIdle < maximumPoolSize
      max-lifetime: 1800000          # Max connection lifetime (ms). Default: 30min
                                     # Set 30s less than DB wait_timeout
      validation-timeout: 5000       # Max time for connection alive check (ms). Default: 5s
      keepalive-time: 300000         # Interval for keepalive pings (ms). Default: 0 (disabled)
                                     # Must be < max-lifetime and > 30s

      # === Connection Testing ===
      connection-test-query: SELECT 1  # Only needed for JDBC3 drivers. Modern drivers use isValid()

      # === Leak Detection ===
      leak-detection-threshold: 60000  # Log warning if connection not returned within (ms)
                                       # Set to longest expected transaction time + buffer

      # === Names & Metrics ===
      pool-name: MainPool
      register-mbeans: true            # JMX monitoring
      metrics-tracker-factory: io.micrometer.core.instrument.binder.db.HikariMetricsTrackerFactory

      # === Initialization ===
      initialization-fail-timeout: 1   # Fail fast if pool can't be created (ms)
                                       # Set to 0 to allow startup without DB
      auto-commit: false               # Let Spring manage commits. IMPORTANT for correctness.

      # === Advanced ===
      transaction-isolation: TRANSACTION_READ_COMMITTED
      catalog: mydb
      schema: public
      read-only: false                 # Default for connections (can override per-transaction)
      isolate-internal-queries: false
      allow-pool-suspension: false     # Only for failover scenarios
```

### Pool Sizing Formula

```
Optimal Pool Size = (Core_Count * 2) + Effective_Spindle_Count

Where:
- Core_Count = number of CPU cores available to the JVM
- Effective_Spindle_Count = number of independent disk spindles (0 for SSD/NVMe)

Examples:
- 4-core server with SSD: (4 * 2) + 0 = 8 connections
- 8-core server with SSD: (8 * 2) + 0 = 16 connections
- 8-core with RAID-10 (4 spindles): (8 * 2) + 4 = 20 connections

Critical insight: A smaller pool with a longer queue WILL outperform
a larger pool. Beyond the optimal size, context switching and cache
invalidation REDUCE throughput.

For multiple microservices sharing one DB:
  Total connections across all instances ≤ DB max_connections * 0.8
  Per-instance pool = (DB_max * 0.8) / instance_count
```

### HikariCP Metrics with Micrometer

```java
@Configuration
public class HikariMetricsConfig {

    @Bean
    public MeterBinder hikariMetrics(DataSource dataSource) {
        HikariDataSource hikariDS = (HikariDataSource) dataSource;
        hikariDS.setMetricRegistry(meterRegistry);
        return new HikariCPMetrics(hikariDS.getHikariPoolMXBean(), "main-pool", Tags.empty());
    }
}
```

Key HikariCP metrics exposed:

| Metric | Meaning | Alert Threshold |
|--------|---------|-----------------|
| `hikaricp_connections_active` | Currently borrowed connections | > 80% of max |
| `hikaricp_connections_idle` | Idle connections in pool | Monitor trend |
| `hikaricp_connections_pending` | Threads waiting for connection | > 0 sustained |
| `hikaricp_connections_timeout_total` | Connection acquisition timeouts | Any non-zero |
| `hikaricp_connections_creation_seconds` | Time to create new connections | > 1s |
| `hikaricp_connections_usage_seconds` | Time connections are held out | > 5s |
| `hikaricp_connections_max` | Maximum pool size | Reference |
| `hikaricp_connections_min` | Minimum idle connections | Reference |

### Diagnosing Pool Exhaustion

```
Symptoms:
1. HikariPool-1 - Connection is not available, request timed out after 30000ms
2. Increasing hikaricp_connections_pending metric
3. Response times spike across all endpoints simultaneously
4. Thread dump shows many threads TIMED_WAITING on HikariPool.getConnection()

Root Causes & Fixes:

┌─────────────────────────────────────┬──────────────────────────────────────────┐
│ Cause                               │ Fix                                      │
├─────────────────────────────────────┼──────────────────────────────────────────┤
│ Long-running transactions           │ Break into smaller units of work         │
│ N+1 queries holding connection      │ Fix fetch strategy, use JOIN FETCH       │
│ External API calls inside @Tx       │ Move external calls outside transaction  │
│ Connection leak (not returned)      │ Enable leak detection, fix code          │
│ Pool too small for load             │ Scale horizontally, not pool size        │
│ Slow queries blocking pool          │ Add indexes, optimize queries            │
│ Deadlocks holding connections       │ Fix ordering, reduce isolation level     │
│ OSIV holding connection for view    │ Disable OSIV                             │
└─────────────────────────────────────┴──────────────────────────────────────────┘
```

### Leak Detection Deep Dive

```java
@Slf4j
@Aspect
@Component
public class ConnectionLeakDetector {

    @Around("@annotation(org.springframework.transaction.annotation.Transactional)")
    public Object detectLeak(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.currentTimeMillis();
        String method = pjp.getSignature().toShortString();

        try {
            return pjp.proceed();
        } finally {
            long duration = System.currentTimeMillis() - start;
            if (duration > 30_000) {
                log.warn("POTENTIAL_LEAK: {} held connection for {}ms. Stack: {}",
                    method, duration, captureStack());
            }
        }
    }

    private String captureStack() {
        return Arrays.stream(Thread.currentThread().getStackTrace())
            .skip(2)
            .limit(10)
            .map(StackTraceElement::toString)
            .collect(Collectors.joining("\n  "));
    }
}
```

### Pool Exhaustion Alert Rules

```yaml
groups:
  - name: connection_pool_alerts
    rules:
      - alert: ConnectionPoolNearExhaustion
        expr: hikaricp_connections_active / hikaricp_connections_max > 0.8
        for: 2m
        labels:
          severity: warning

      - alert: ConnectionPoolExhausted
        expr: hikaricp_connections_pending > 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Threads waiting for connections"

      - alert: ConnectionTimeouts
        expr: rate(hikaricp_connections_timeout_total[5m]) > 0
        for: 1m
        labels:
          severity: critical

      - alert: ConnectionCreationSlow
        expr: hikaricp_connections_creation_seconds_max > 2
        for: 1m
        labels:
          severity: warning

      - alert: ConnectionHeldTooLong
        expr: histogram_quantile(0.99, hikaricp_connections_usage_seconds_bucket) > 10
        for: 5m
        labels:
          severity: warning
```

---

## 4. Transaction Monitoring

### Transaction Duration Tracking with AOP

```java
@Aspect
@Component
@Slf4j
public class TransactionMetricsAspect {

    private final MeterRegistry meterRegistry;
    private final Timer transactionTimer;
    private final Counter rollbackCounter;
    private final Counter commitCounter;
    private final DistributionSummary entityCountSummary;

    public TransactionMetricsAspect(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        this.transactionTimer = Timer.builder("jpa.transaction.duration")
            .description("Transaction duration")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
        this.rollbackCounter = Counter.builder("jpa.transaction.rollback")
            .description("Transaction rollbacks")
            .register(meterRegistry);
        this.commitCounter = Counter.builder("jpa.transaction.commit")
            .description("Transaction commits")
            .register(meterRegistry);
        this.entityCountSummary = DistributionSummary.builder("jpa.transaction.entity_count")
            .description("Entities managed per transaction")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
    }

    @Around("@annotation(transactional)")
    public Object measureTransaction(ProceedingJoinPoint pjp,
                                      Transactional transactional) throws Throwable {
        String methodName = pjp.getSignature().toShortString();
        Timer.Sample sample = Timer.start(meterRegistry);

        try {
            Object result = pjp.proceed();
            commitCounter.increment();
            sample.stop(Timer.builder("jpa.transaction.duration")
                .tag("method", methodName)
                .tag("outcome", "commit")
                .register(meterRegistry));
            return result;
        } catch (Exception ex) {
            rollbackCounter.increment();
            sample.stop(Timer.builder("jpa.transaction.duration")
                .tag("method", methodName)
                .tag("outcome", "rollback")
                .register(meterRegistry));

            meterRegistry.counter("jpa.transaction.rollback",
                "method", methodName,
                "exception", ex.getClass().getSimpleName()
            ).increment();

            throw ex;
        }
    }
}
```

### Long Transaction Detection

```java
@Component
public class LongTransactionDetector {

    private final ConcurrentHashMap<Long, TransactionInfo> activeTransactions =
        new ConcurrentHashMap<>();

    @EventListener
    public void onTransactionStart(TransactionStartEvent event) {
        activeTransactions.put(Thread.currentThread().getId(),
            new TransactionInfo(System.currentTimeMillis(),
                Thread.currentThread().getStackTrace()));
    }

    @Scheduled(fixedRate = 5000)
    public void checkLongTransactions() {
        long now = System.currentTimeMillis();
        activeTransactions.forEach((threadId, info) -> {
            long duration = now - info.startTime();
            if (duration > 30_000) {
                log.warn("LONG_TRANSACTION: thread={} duration={}ms started_at={}",
                    threadId, duration,
                    Arrays.stream(info.stackTrace())
                        .skip(3).limit(5)
                        .map(StackTraceElement::toString)
                        .collect(Collectors.joining(" -> ")));
            }
        });
    }

    record TransactionInfo(long startTime, StackTraceElement[] stackTrace) {}
}
```

### Optimistic Lock Failure Rate Tracking

```java
@Aspect
@Component
public class OptimisticLockMonitor {

    private final Counter optimisticLockFailures;

    public OptimisticLockMonitor(MeterRegistry registry) {
        this.optimisticLockFailures = Counter.builder("jpa.optimistic_lock.failure")
            .description("Optimistic locking failures")
            .register(registry);
    }

    @AfterThrowing(
        pointcut = "execution(* org.springframework.data.jpa.repository.JpaRepository+.*(..))",
        throwing = "ex"
    )
    public void countOptimisticLockFailures(ObjectOptimisticLockingFailureException ex) {
        optimisticLockFailures.increment();
        log.warn("Optimistic lock failure: entity={} id={}",
            ex.getPersistentClassName(), ex.getIdentifier());
    }
}

// Retry mechanism for optimistic lock failures
@Retryable(
    retryFor = ObjectOptimisticLockingFailureException.class,
    maxAttempts = 3,
    backoff = @Backoff(delay = 100, multiplier = 2)
)
@Transactional
public Order updateOrderStatus(Long orderId, OrderStatus newStatus) {
    Order order = orderRepository.findById(orderId)
        .orElseThrow(() -> new OrderNotFoundException(orderId));
    order.setStatus(newStatus);
    return orderRepository.save(order);
}
```

---

## 5. N+1 Detection in Production

### Runtime Detection Using StatementInspector

```java
@Component
public class NPlus1Detector implements StatementInspector {

    private static final ThreadLocal<QueryTracker> TRACKER = new ThreadLocal<>();
    private final MeterRegistry meterRegistry;

    public NPlus1Detector(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    @Override
    public String inspect(String sql) {
        QueryTracker tracker = TRACKER.get();
        if (tracker != null) {
            tracker.record(sql);
        }
        return sql;
    }

    public static void startTracking(String operationName) {
        TRACKER.set(new QueryTracker(operationName));
    }

    public static QueryTracker stopTracking() {
        QueryTracker tracker = TRACKER.get();
        TRACKER.remove();
        return tracker;
    }

    @Slf4j
    public static class QueryTracker {
        private final String operation;
        private final List<String> queries = new ArrayList<>();
        private final Map<String, Integer> queryPatternCounts = new HashMap<>();

        QueryTracker(String operation) {
            this.operation = operation;
        }

        void record(String sql) {
            queries.add(sql);
            // Normalize: replace literals with ?
            String pattern = sql.replaceAll("'[^']*'", "?")
                               .replaceAll("\\b\\d+\\b", "?")
                               .replaceAll("\\s+", " ")
                               .trim();
            queryPatternCounts.merge(pattern, 1, Integer::sum);
        }

        public boolean hasNPlus1() {
            return queryPatternCounts.values().stream()
                .anyMatch(count -> count > 5);
        }

        public Map<String, Integer> getSuspiciousPatterns() {
            return queryPatternCounts.entrySet().stream()
                .filter(e -> e.getValue() > 5)
                .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
        }

        public int getTotalQueryCount() {
            return queries.size();
        }
    }
}
```

### Request-Scoped N+1 Detection Filter

```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class NPlus1DetectionFilter extends OncePerRequestFilter {

    private final MeterRegistry meterRegistry;
    private static final int QUERY_THRESHOLD = 20;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String operation = request.getMethod() + " " + request.getRequestURI();
        NPlus1Detector.startTracking(operation);

        try {
            chain.doFilter(request, response);
        } finally {
            NPlus1Detector.QueryTracker tracker = NPlus1Detector.stopTracking();
            if (tracker != null) {
                int queryCount = tracker.getTotalQueryCount();

                meterRegistry.summary("http.request.query_count",
                    "uri", request.getRequestURI(),
                    "method", request.getMethod()
                ).record(queryCount);

                if (queryCount > QUERY_THRESHOLD) {
                    log.warn("HIGH_QUERY_COUNT: {} executed {} queries. " +
                             "Suspicious patterns: {}",
                        operation, queryCount, tracker.getSuspiciousPatterns());
                }

                if (tracker.hasNPlus1()) {
                    log.error("N+1_DETECTED: {} patterns: {}",
                        operation, tracker.getSuspiciousPatterns());

                    meterRegistry.counter("jpa.nplus1.detected",
                        "operation", operation).increment();
                }
            }
        }
    }
}
```

### APM Integration Patterns

```java
// For APM tools like New Relic, Datadog, Elastic APM:
// They instrument JDBC drivers and correlate queries to transactions.
// Key integration points:

// 1. Span-per-query: Each SQL becomes a child span of the HTTP span
// 2. Query grouping: Similar queries (different params) are grouped
// 3. N+1 detection: >N similar queries in one transaction flagged

// Custom span annotation for explicit tracking
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface TrackQueries {
    String operation() default "";
    int alertThreshold() default 10;
}

@Aspect
@Component
public class QueryTrackingAspect {

    @Around("@annotation(trackQueries)")
    public Object trackQueries(ProceedingJoinPoint pjp,
                                TrackQueries trackQueries) throws Throwable {
        NPlus1Detector.startTracking(trackQueries.operation());
        try {
            return pjp.proceed();
        } finally {
            var tracker = NPlus1Detector.stopTracking();
            if (tracker != null && tracker.getTotalQueryCount() > trackQueries.alertThreshold()) {
                log.warn("Query budget exceeded for {}: {} > {}",
                    trackQueries.operation(),
                    tracker.getTotalQueryCount(),
                    trackQueries.alertThreshold());
            }
        }
    }
}
```

---

## 6. Second-Level Cache Monitoring

### Hit Ratio Monitoring

```java
@Component
@Slf4j
public class CacheMetricsCollector {

    private final EntityManagerFactory emf;
    private final MeterRegistry registry;

    @Scheduled(fixedRate = 30_000)
    public void reportCacheMetrics() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();

        long hits = stats.getSecondLevelCacheHitCount();
        long misses = stats.getSecondLevelCacheMissCount();
        long puts = stats.getSecondLevelCachePutCount();

        double hitRatio = (hits + misses) == 0 ? 0 :
            (double) hits / (hits + misses);

        registry.gauge("hibernate.cache.l2.hit_ratio", hitRatio);

        if (hitRatio < 0.9 && (hits + misses) > 100) {
            log.warn("L2 cache hit ratio below target: {:.2f}% (hits={}, misses={}, puts={})",
                hitRatio * 100, hits, misses, puts);
        }

        // Per-region metrics
        Arrays.stream(stats.getSecondLevelCacheRegionNames())
            .forEach(region -> {
                CacheRegionStatistics regionStats =
                    stats.getDomainDataRegionStatistics(region);
                registry.gauge("hibernate.cache.region.hit_ratio",
                    Tags.of("region", region),
                    regionStats,
                    rs -> {
                        long h = rs.getHitCount();
                        long m = rs.getMissCount();
                        return (h + m) == 0 ? 0 : (double) h / (h + m);
                    });
                registry.gauge("hibernate.cache.region.size",
                    Tags.of("region", region),
                    regionStats, CacheRegionStatistics::getElementCountInMemory);
            });
    }
}
```

### Cache Warming Strategies

```java
// Strategy 1: Startup warming (small reference data)
@Component
@Slf4j
public class CacheWarmer implements ApplicationRunner {

    private final EntityManagerFactory emf;
    private final CountryRepository countryRepository;
    private final CurrencyRepository currencyRepository;
    private final ConfigRepository configRepository;

    @Override
    @Transactional(readOnly = true)
    public void run(ApplicationArguments args) {
        log.info("Warming L2 cache...");
        Instant start = Instant.now();

        // Force load into L2 cache
        countryRepository.findAll();           // ~250 entities
        currencyRepository.findAll();          // ~180 entities
        configRepository.findAllActive();      // ~50 entities

        log.info("Cache warming complete in {}ms",
            Duration.between(start, Instant.now()).toMillis());
    }
}

// Strategy 2: Background refresh (periodic cache population)
@Component
public class CacheRefresher {

    private final Cache cache;
    private final ProductRepository productRepository;

    @Scheduled(fixedRate = 300_000) // Every 5 minutes
    @Async("cacheRefreshExecutor")
    public void refreshPopularProducts() {
        List<Long> popularIds = productRepository.findPopularProductIds(100);
        // Batch load to avoid N+1 on cache miss storms
        productRepository.findAllById(popularIds); // Populates L2 cache
    }
}

// Strategy 3: Lazy warming with miss tracking
@Component
public class SmartCacheWarmer {

    private final ConcurrentHashMap<String, AtomicLong> missCounters =
        new ConcurrentHashMap<>();

    // Called on cache miss events
    public void recordMiss(String region, Object id) {
        String key = region + ":" + id;
        long count = missCounters.computeIfAbsent(key, k -> new AtomicLong())
            .incrementAndGet();

        if (count > 10) {
            // This entity is frequently missed - pre-warm it
            scheduleWarm(region, id);
        }
    }

    @Scheduled(fixedRate = 60_000)
    public void pruneCounters() {
        missCounters.entrySet().removeIf(e -> e.getValue().get() < 5);
    }
}
```

### Thundering Herd Detection & Prevention

```java
// Problem: Cache entry expires, N concurrent requests all miss and hit DB

// Solution 1: Lock on cache miss (Caffeine async loading)
@Configuration
public class CacheConfig {

    @Bean
    public CacheManager cacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(Duration.ofMinutes(5))
            .refreshAfterWrite(Duration.ofMinutes(4))  // Async refresh before expiry
            .recordStats());
        return manager;
    }
}

// Solution 2: Probabilistic early expiration
@Component
public class ThunderingHerdProtection {

    private final MeterRegistry registry;

    /**
     * XFetch algorithm: probabilistically refresh before expiry
     * to prevent all instances from expiring simultaneously.
     */
    public <T> T getWithEarlyRefresh(Cache cache, String key,
                                      Duration ttl, Supplier<T> loader) {
        CacheEntry<T> entry = cache.get(key);

        if (entry == null) {
            // Hard miss - load and cache
            T value = loader.get();
            cache.put(key, new CacheEntry<>(value, Instant.now(), ttl));
            registry.counter("cache.miss", "key", key).increment();
            return value;
        }

        // Probabilistic early refresh
        double elapsed = Duration.between(entry.createdAt(), Instant.now()).toMillis();
        double beta = 1.0; // tuning parameter
        double randomRefreshTime = entry.ttl().toMillis() -
            (beta * Math.log(Math.random()) * elapsed);

        if (System.currentTimeMillis() > entry.createdAt().toEpochMilli() + randomRefreshTime) {
            // Refresh in background, serve stale
            CompletableFuture.runAsync(() -> {
                T fresh = loader.get();
                cache.put(key, new CacheEntry<>(fresh, Instant.now(), ttl));
            });
            registry.counter("cache.early_refresh", "key", key).increment();
        }

        return entry.value();
    }

    record CacheEntry<T>(T value, Instant createdAt, Duration ttl) {}
}
```

### Cache Invalidation Monitoring in Clustered Environments

```yaml
# Infinispan/Hazelcast cluster cache config
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region.factory_class: infinispan
      javax:
        persistence:
          sharedCache:
            mode: ENABLE_SELECTIVE
```

```java
@Component
@Slf4j
public class CacheInvalidationMonitor {

    private final MeterRegistry registry;

    // Track invalidation events
    @EventListener
    public void onCacheInvalidation(CacheEntryInvalidatedEvent event) {
        registry.counter("cache.invalidation",
            "region", event.getRegion(),
            "source", event.isOriginLocal() ? "local" : "remote"
        ).increment();

        if (!event.isOriginLocal()) {
            log.debug("Remote cache invalidation: region={} key={}",
                event.getRegion(), event.getKey());
        }
    }

    // Detect invalidation storms
    @Scheduled(fixedRate = 10_000)
    public void detectInvalidationStorm() {
        double rate = registry.get("cache.invalidation")
            .counter().count(); // Check rate over window

        if (rate > 1000) {
            log.error("CACHE_INVALIDATION_STORM: {} invalidations in last 10s", rate);
        }
    }
}
```

---

## 7. Database Migration in Production

### Zero-Downtime Schema Changes (Expand-Contract Pattern)

```
Phase 1: EXPAND (backward compatible)
────────────────────────────────────────
1. Add new column (nullable, with default)
2. Deploy code that writes to BOTH old and new columns
3. Backfill new column from old column
4. Deploy code that reads from new column

Phase 2: CONTRACT (cleanup)
────────────────────────────────────────
5. Deploy code that only writes to new column
6. Drop old column

Example: Renaming `user.name` → `user.full_name`
```

```sql
-- V1: Expand - Add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);

-- V2: Backfill (run as background job, not in migration)
UPDATE users SET full_name = name WHERE full_name IS NULL LIMIT 10000;
-- Repeat until done

-- V3: Contract - Drop old column (weeks later, after all code migrated)
ALTER TABLE users DROP COLUMN name;
```

### Flyway Migration with Dual-Write Entity

```java
// During migration phase - entity supports both columns
@Entity
@Table(name = "users")
public class User {

    @Column(name = "full_name")
    private String fullName;

    // Keep old column mapped during transition
    @Column(name = "name", insertable = false, updatable = false)
    private String legacyName;

    @PrePersist
    @PreUpdate
    public void syncColumns() {
        // Dual-write during transition
        // Handled at DB level with trigger or in repository
    }
}
```

### Online Schema Change Tools

```bash
# PostgreSQL: pg_repack (reclaims space, rebuilds indexes without locks)
pg_repack --table=orders --no-superuser-check -d mydb

# MySQL: gh-ost (GitHub Online Schema Migration)
gh-ost \
  --host=replica.db.internal \
  --database=myapp \
  --table=orders \
  --alter="ADD COLUMN tracking_number VARCHAR(100)" \
  --execute \
  --allow-on-master \
  --chunk-size=1000 \
  --max-load="Threads_running=25"

# MySQL: pt-online-schema-change (Percona)
pt-online-schema-change \
  --alter "ADD COLUMN tracking_number VARCHAR(100)" \
  D=myapp,t=orders \
  --execute \
  --max-load Threads_running=25 \
  --chunk-size 1000
```

### Flyway Production Best Practices

```yaml
spring:
  flyway:
    enabled: true
    baseline-on-migrate: true
    baseline-version: 0
    locations: classpath:db/migration
    validate-on-migrate: true
    out-of-order: false           # Never allow in production
    clean-disabled: true          # NEVER allow clean in production
    group: true                   # Wrap all pending migrations in single transaction
    lock-retry-count: 50          # Retry if another instance holds migration lock
    installed-by: ${HOSTNAME}     # Track which instance applied migration
```

```
Production Migration Rules:
━━━━━━━━━━━━━━━━━━━━━━━━━━
1. NEVER modify an already-applied migration
2. NEVER delete a migration file
3. All DDL must be backward-compatible with previous code version
4. Large data migrations → background jobs, NOT migration scripts
5. Always test migrations against production-size data copy
6. Migrations must be idempotent where possible
7. Include rollback script in comments (but never auto-rollback DDL)
8. Maximum execution time per migration: 30 seconds
9. Lock timeout: SET lock_timeout = '5s' at start of each migration
```

```sql
-- Example: Safe migration with guard rails
-- V42__add_tracking_number.sql

SET lock_timeout = '5s';
SET statement_timeout = '30s';

-- Idempotent: check before adding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'tracking_number'
    ) THEN
        ALTER TABLE orders ADD COLUMN tracking_number VARCHAR(100);
    END IF;
END $$;

-- Index concurrently (doesn't lock table, but can't be in transaction)
-- Use separate migration file for this:
-- V43__add_tracking_number_index.sql
-- spring.flyway.group=false for this one
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_tracking
    ON orders(tracking_number);
```

### Large Data Migration Pattern

```java
// Background job for large data migrations - NOT in Flyway
@Component
@Slf4j
public class DataMigrationJob {

    private final JdbcTemplate jdbc;
    private final MeterRegistry registry;

    @Scheduled(fixedDelay = 1000)
    @DistributedLock(name = "data-migration-v42", ttl = 300)
    public void migrateInBatches() {
        int batchSize = 1000;
        int totalMigrated = 0;

        while (true) {
            int updated = jdbc.update("""
                UPDATE orders
                SET tracking_number = legacy_tracking
                WHERE tracking_number IS NULL
                  AND legacy_tracking IS NOT NULL
                LIMIT ?
                """, batchSize);

            totalMigrated += updated;
            registry.counter("migration.v42.rows").increment(updated);

            if (updated < batchSize) {
                log.info("Migration V42 complete. Total rows: {}", totalMigrated);
                break;
            }

            // Throttle to avoid overwhelming the database
            sleep(100);
        }
    }
}
```

---

## 8. Production Anti-Patterns & Solutions

### OSIV (Open Session In View) — Disable It

```yaml
# MUST disable in production
spring:
  jpa:
    open-in-view: false  # Default is TRUE (dangerous!)
```

```
Why OSIV is dangerous in production:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Holds database connection for ENTIRE HTTP request lifecycle
2. Lazy loading in view/controller triggers unpredictable queries
3. Connection pool exhaustion under load (connection held during
   serialization, template rendering, even slow client reads)
4. N+1 queries hidden in templates/serialization
5. Impossible to reason about transaction boundaries

Fix: Use DTOs, fetch all needed data in @Service/@Transactional methods
```

### Entity Exposure in REST APIs

```java
// WRONG: Exposing entity directly
@GetMapping("/users/{id}")
public User getUser(@PathVariable Long id) {
    return userRepository.findById(id).orElseThrow();
    // Problems: lazy loading exceptions, circular refs, over-fetching,
    // security (exposes internal fields), tight coupling
}

// CORRECT: DTO projection
@GetMapping("/users/{id}")
public UserResponse getUser(@PathVariable Long id) {
    return userService.getUserById(id); // Returns DTO
}

// Best: Spring Data projection
public interface UserSummary {
    Long getId();
    String getFullName();
    String getEmail();
}

@Query("SELECT u.id as id, u.fullName as fullName, u.email as email FROM User u WHERE u.id = :id")
Optional<UserSummary> findSummaryById(@Param("id") Long id);
```

### Missing Pagination

```java
// WRONG: Unbounded query
@GetMapping("/orders")
public List<Order> getAllOrders() {
    return orderRepository.findAll(); // Could return millions
}

// CORRECT: Enforced pagination with max limit
@GetMapping("/orders")
public Page<OrderDto> getOrders(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {

    int maxSize = 100;
    int safeSize = Math.min(size, maxSize);
    Pageable pageable = PageRequest.of(page, safeSize, Sort.by("createdAt").descending());
    return orderService.findOrders(pageable);
}

// Global enforcement
@ControllerAdvice
public class PaginationAdvice {

    @InitBinder
    public void initBinder(WebDataBinder binder) {
        // Enforce across all endpoints
    }
}

// Repository level guard
@Query("SELECT o FROM Order o")
@QueryHints(@QueryHint(name = "org.hibernate.fetchSize", value = "50"))
Page<Order> findAllPaged(Pageable pageable);
```

### Transaction Scope Too Large

```java
// WRONG: @Transactional at controller level
@RestController
@Transactional // NEVER DO THIS
public class OrderController {
    @GetMapping("/orders/{id}")
    public OrderResponse getOrder(@PathVariable Long id) {
        Order order = orderService.find(id);
        // Connection held during JSON serialization!
        emailService.sendNotification(order); // External call inside TX!
        return mapper.toResponse(order);
    }
}

// CORRECT: Minimal transaction scope
@RestController
public class OrderController {

    @GetMapping("/orders/{id}")
    public OrderResponse getOrder(@PathVariable Long id) {
        OrderDto dto = orderService.getOrderDto(id); // TX inside service
        return mapper.toResponse(dto);
    }

    @PostMapping("/orders/{id}/fulfill")
    public OrderResponse fulfillOrder(@PathVariable Long id) {
        OrderDto dto = orderService.fulfill(id);  // Short TX
        eventPublisher.publish(new OrderFulfilledEvent(id));  // Outside TX
        return mapper.toResponse(dto);
    }
}

@Service
public class OrderService {
    @Transactional(readOnly = true)
    public OrderDto getOrderDto(Long id) {
        // Fetch everything needed, return DTO
        // Connection released immediately after this method
    }

    @Transactional
    public OrderDto fulfill(Long id) {
        // Short write transaction
    }
}
```

---

## 9. Disaster Recovery & High Availability

### Read Replica Routing with AbstractRoutingDataSource

```java
public enum DataSourceType {
    PRIMARY, REPLICA
}

public class RoutingDataSource extends AbstractRoutingDataSource {

    private static final ThreadLocal<DataSourceType> CURRENT =
        ThreadLocal.withInitial(() -> DataSourceType.PRIMARY);

    @Override
    protected Object determineCurrentLookupKey() {
        return CURRENT.get();
    }

    public static void setReadOnly(boolean readOnly) {
        CURRENT.set(readOnly ? DataSourceType.REPLICA : DataSourceType.PRIMARY);
    }

    public static void clear() {
        CURRENT.remove();
    }
}

@Configuration
public class DataSourceConfig {

    @Bean
    public DataSource dataSource(
            @Qualifier("primaryDataSource") DataSource primary,
            @Qualifier("replicaDataSource") DataSource replica) {

        RoutingDataSource routing = new RoutingDataSource();
        Map<Object, Object> dataSources = Map.of(
            DataSourceType.PRIMARY, primary,
            DataSourceType.REPLICA, replica
        );
        routing.setTargetDataSources(dataSources);
        routing.setDefaultTargetDataSource(primary);
        return routing;
    }

    @Bean
    @ConfigurationProperties("spring.datasource.primary.hikari")
    public DataSource primaryDataSource() {
        return DataSourceBuilder.create().type(HikariDataSource.class).build();
    }

    @Bean
    @ConfigurationProperties("spring.datasource.replica.hikari")
    public DataSource replicaDataSource() {
        return DataSourceBuilder.create().type(HikariDataSource.class).build();
    }
}

// Automatic routing based on @Transactional(readOnly)
@Aspect
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class ReadOnlyRoutingAspect {

    @Around("@annotation(transactional)")
    public Object route(ProceedingJoinPoint pjp, Transactional transactional) throws Throwable {
        try {
            RoutingDataSource.setReadOnly(transactional.readOnly());
            return pjp.proceed();
        } finally {
            RoutingDataSource.clear();
        }
    }
}
```

### Read-After-Write Consistency with Replication Lag

```java
@Component
public class ReplicationAwareRouter {

    // Track recent writes per user/session
    private final Cache<String, Instant> recentWrites = Caffeine.newBuilder()
        .expireAfterWrite(Duration.ofSeconds(10)) // Max expected replication lag
        .build();

    private final Duration maxReplicationLag = Duration.ofSeconds(5);

    public DataSourceType determineDataSource(boolean readOnly, String sessionId) {
        if (!readOnly) {
            // Writes always go to primary
            recentWrites.put(sessionId, Instant.now());
            return DataSourceType.PRIMARY;
        }

        // Check if this session recently wrote
        Instant lastWrite = recentWrites.getIfPresent(sessionId);
        if (lastWrite != null &&
            Duration.between(lastWrite, Instant.now()).compareTo(maxReplicationLag) < 0) {
            // Recent write - route to primary to ensure consistency
            return DataSourceType.PRIMARY;
        }

        return DataSourceType.REPLICA;
    }
}
```

### Failover Handling with Resilience4j

```yaml
spring:
  datasource:
    primary:
      hikari:
        maximum-pool-size: 10
        connection-timeout: 5000       # Fail fast on primary down
        validation-timeout: 3000
        max-lifetime: 1800000
        keepalive-time: 60000          # Detect dead connections quickly

resilience4j:
  retry:
    instances:
      database:
        max-attempts: 3
        wait-duration: 500ms
        retry-exceptions:
          - java.sql.SQLTransientConnectionException
          - org.hibernate.exception.JDBCConnectionException
          - org.springframework.dao.TransientDataAccessException
        ignore-exceptions:
          - org.springframework.dao.DataIntegrityViolationException
  circuitbreaker:
    instances:
      database:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 30s
        permitted-number-of-calls-in-half-open-state: 3
```

```java
@Service
@Slf4j
public class ResilientOrderService {

    private final OrderRepository orderRepository;
    private final RetryRegistry retryRegistry;
    private final CircuitBreakerRegistry cbRegistry;

    @Transactional
    @CircuitBreaker(name = "database", fallbackMethod = "fallbackGetOrder")
    @Retry(name = "database")
    public OrderDto getOrder(Long id) {
        return orderRepository.findById(id)
            .map(OrderMapper::toDto)
            .orElseThrow(() -> new OrderNotFoundException(id));
    }

    private OrderDto fallbackGetOrder(Long id, Exception ex) {
        log.error("Database circuit open for getOrder({}): {}", id, ex.getMessage());
        // Return cached version, or throw specific exception for client retry
        throw new ServiceUnavailableException("Database temporarily unavailable", ex);
    }
}
```

### Sequence/ID Gap Handling After Recovery

```java
/*
 * After failover, sequences may have gaps due to:
 * 1. Pre-allocated sequence values lost in crashed instance
 * 2. Rolled-back transactions consuming sequence values
 *
 * Solutions:
 * - Never rely on gapless sequences for business logic
 * - Use separate "order_number" sequence if gaps matter
 * - For audit: detect and log gaps, don't prevent them
 */

@Component
@Slf4j
public class SequenceGapDetector {

    @Scheduled(fixedRate = 60_000)
    public void detectGaps() {
        // Only for monitoring/alerting, not for preventing gaps
        Long maxId = jdbc.queryForObject(
            "SELECT MAX(id) FROM orders", Long.class);
        Long count = jdbc.queryForObject(
            "SELECT COUNT(*) FROM orders", Long.class);

        if (maxId != null && count != null) {
            long gaps = maxId - count;
            if (gaps > 1000) {
                log.warn("Significant ID gaps in orders table: {} gaps (max_id={}, count={})",
                    gaps, maxId, count);
            }
        }
    }
}
```

---

## 10. Observability Stack Integration

### Complete Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Spring Boot Application                       │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ Hibernate │  │  HikariCP    │  │  Spring TX │  │  App Logic   │ │
│  │ Statistics│  │  Metrics     │  │  Metrics   │  │  Metrics     │ │
│  └─────┬────┘  └──────┬───────┘  └─────┬──────┘  └──────┬───────┘ │
│        │               │                │                │         │
│        └───────────────┴────────────────┴────────────────┘         │
│                                │                                    │
│                    ┌───────────┴───────────┐                       │
│                    │   Micrometer Registry  │                       │
│                    └───────────┬───────────┘                       │
│                                │                                    │
│                    ┌───────────┴───────────┐                       │
│                    │  /actuator/prometheus  │                       │
│                    └───────────┬───────────┘                       │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ scrape
                    ┌────────────┴────────────┐
                    │       Prometheus         │
                    │  (time-series storage)   │
                    └────────────┬────────────┘
                                 │ query
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────┴──────┐  ┌───────┴───────┐  ┌───────┴───────┐
    │    Grafana      │  │  AlertManager  │  │   PagerDuty   │
    │  (dashboards)   │  │  (routing)     │  │  (on-call)    │
    └────────────────┘  └───────────────┘  └───────────────┘
```

### Key Dashboards

**Dashboard 1: JPA Operations Overview**
- Query execution rate (by type: SELECT, INSERT, UPDATE, DELETE)
- Entity operations (loads, fetches, inserts, updates, deletes)
- Query count per request (p50, p95, p99)
- Flush operations rate
- N+1 detection alerts timeline

**Dashboard 2: Connection Pool Health**
- Active vs idle vs max connections (stacked area)
- Pending connection requests (should be 0)
- Connection acquisition time (p95, p99)
- Connection usage duration (p95, p99)
- Timeout events timeline
- Connection creation rate

**Dashboard 3: Cache Performance**
- L2 cache hit ratio (per region, overall)
- Query cache hit ratio
- Cache put/eviction rate
- Cache size per region
- Invalidation events (local vs remote)

**Dashboard 4: Query Performance**
- Slowest queries (max execution time)
- Query execution time distribution
- Queries per second by endpoint
- Database response time percentiles

**Dashboard 5: Transaction Health**
- Transaction commit/rollback rate
- Transaction duration (p50, p95, p99)
- Optimistic lock failures rate
- Long transaction alerts

### Complete Alerting Rules Checklist

```yaml
groups:
  - name: jpa_production_alerts
    rules:
      # 1. Connection Pool
      - alert: ConnectionPoolExhausted
        expr: hikaricp_connections_pending > 0
        for: 30s
        labels: { severity: critical }

      - alert: ConnectionPoolHighUtilization
        expr: hikaricp_connections_active / hikaricp_connections_max > 0.85
        for: 2m
        labels: { severity: warning }

      - alert: ConnectionTimeout
        expr: increase(hikaricp_connections_timeout_total[5m]) > 0
        labels: { severity: critical }

      - alert: ConnectionLeakSuspected
        expr: hikaricp_connections_usage_seconds{quantile="0.99"} > 30
        for: 5m
        labels: { severity: warning }

      # 2. Query Performance
      - alert: HighQueryCountPerRequest
        expr: histogram_quantile(0.95, rate(request_query_count_bucket[5m])) > 20
        for: 5m
        labels: { severity: warning }

      - alert: SlowQueryDetected
        expr: hibernate_queries_max_time > 5000
        for: 1m
        labels: { severity: warning }

      - alert: NPlusOneDetected
        expr: rate(jpa_nplus1_detected_total[5m]) > 0
        for: 1m
        labels: { severity: warning }

      # 3. Cache
      - alert: LowL2CacheHitRatio
        expr: hibernate_cache_l2_hit_ratio < 0.7
        for: 10m
        labels: { severity: warning }

      - alert: CacheInvalidationStorm
        expr: rate(cache_invalidation_total[1m]) > 100
        for: 2m
        labels: { severity: warning }

      # 4. Transactions
      - alert: HighRollbackRate
        expr: >
          rate(jpa_transaction_rollback_total[5m]) /
          (rate(jpa_transaction_commit_total[5m]) + rate(jpa_transaction_rollback_total[5m])) > 0.05
        for: 5m
        labels: { severity: warning }

      - alert: LongRunningTransaction
        expr: jpa_transaction_duration_seconds{quantile="0.99"} > 30
        for: 5m
        labels: { severity: warning }

      - alert: HighOptimisticLockFailures
        expr: rate(hibernate_optimistic_lock_failures_total[5m]) > 5
        for: 5m
        labels: { severity: warning }

      # 5. Entity Operations
      - alert: ExcessiveEntityLoading
        expr: rate(hibernate_entities_load_total[5m]) > 10000
        for: 5m
        labels: { severity: warning }

      - alert: HighFlushRate
        expr: rate(hibernate_flushes_total[5m]) > 100
        for: 5m
        labels: { severity: warning }

      # 6. Database Health
      - alert: DatabaseConnectionFailure
        expr: up{job="spring-app"} == 0
        for: 1m
        labels: { severity: critical }

      - alert: ReplicationLagHigh
        expr: pg_replication_lag_seconds > 5
        for: 2m
        labels: { severity: warning }
```

### Production Runbook Entries

#### Runbook: Connection Pool Exhaustion

```markdown
## Symptom
- Alert: ConnectionPoolExhausted
- Users see: 503 Service Unavailable or extreme latency
- Logs: "HikariPool-1 - Connection is not available, request timed out"

## Immediate Actions
1. Check active connections: `hikaricp_connections_active`
2. Thread dump: `curl localhost:8080/actuator/threaddump | grep -A5 TIMED_WAITING`
3. Look for threads waiting on `HikariPool.getConnection`

## Diagnosis
- If connections held long: check `hikaricp_connections_usage_seconds` → long transactions
- If many pending: check if DB is responding → `SELECT 1` test
- If leak detection fires: check logs for "Connection leak detection triggered"

## Fixes
- Short term: Restart affected pods (rolling)
- If OSIV: Verify `spring.jpa.open-in-view=false`
- If long TX: Identify via long transaction alert, optimize
- If external call in TX: Refactor to move outside @Transactional
- If true overload: Scale horizontally (more pods, not bigger pool)
```

#### Runbook: N+1 Query Detected

```markdown
## Symptom
- Alert: HighQueryCountPerRequest or NPlusOneDetected
- High `hibernate_entities_fetch` relative to `hibernate_entities_load`
- Similar SELECT statements repeated in logs

## Diagnosis
1. Identify endpoint: check `request_query_count` tagged by URI
2. Check SQL logs for repeated patterns (same table, different WHERE)
3. Find the entity relationship causing lazy loads

## Fixes
- Add @EntityGraph or JOIN FETCH to repository method
- Use @BatchSize(size=20) on collection for bulk fetch
- Switch to DTO projection if full entity not needed
- For lists: use IN clause batch fetching

## Prevention
- N+1 detection in integration tests
- Query count assertions per endpoint
- Code review checklist item
```

#### Runbook: Optimistic Lock Storm

```markdown
## Symptom
- Alert: HighOptimisticLockFailures
- Users see: 409 Conflict or retry errors
- High contention on specific entities

## Diagnosis
1. Identify entity: check logs for entity class and ID
2. Check concurrent access patterns
3. Determine if legitimate concurrency or bug

## Fixes
- Add @Retryable with backoff for expected contention
- Reduce transaction scope to minimize lock window
- Consider pessimistic lock for hot spots: @Lock(PESSIMISTIC_WRITE)
- Redesign: split hot entity into less-contended aggregates
- Queue writes to hot entities through serialized processor
```

#### Runbook: L2 Cache Hit Ratio Drop

```markdown
## Symptom
- Alert: LowL2CacheHitRatio
- Increased database load
- Higher response times

## Diagnosis
1. Check per-region stats: which region degraded?
2. Check invalidation rate: spike in evictions?
3. Check if deployment cleared caches
4. Check if data access pattern changed

## Fixes
- Post-deployment: wait for cache to warm (or add warming)
- If invalidation storm: check for bulk update operations
- If working set grew: increase cache size
- If pattern changed: review cache strategy for affected entities
- Consider TTL tuning per region
```

---

## Summary: Production Readiness Checklist

```
□ spring.jpa.open-in-view=false
□ Hibernate statistics enabled with Micrometer export
□ HikariCP metrics registered (pool size, active, pending, timeout)
□ Connection pool sized correctly (cores * 2 formula)
□ Leak detection enabled (threshold = max expected TX time + 50%)
□ Slow query logging enabled (Hibernate + database level)
□ SQL correlated with trace IDs via MDC/comments
□ N+1 detection active (StatementInspector + per-request counting)
□ L2 cache monitored with hit ratio alerts (target > 90%)
□ Transaction duration tracked with AOP
□ Optimistic lock failures counted and alerted
□ Read replicas configured with consistency handling
□ Retry + circuit breaker for transient DB failures
□ All entities use DTOs at API boundary
□ Pagination enforced with max page size
□ Flyway migrations follow zero-downtime pattern
□ Alerting rules configured for all key metrics
□ Runbooks written for top 5 failure scenarios
□ Grafana dashboards for pool, cache, queries, transactions
□ Load tested with production-like data volume
```
