# Observability & Distributed Tracing - Staff Engineer / Architect Level

## Target Level: Staff Engineer / Architect
These problems focus on designing and operating observability systems at scale -- a critical staff-level competency. Not just "add logging" but building comprehensive observability platforms.

---

## Problem 1: Design an Observability Strategy for 200 Microservices

**Scenario:** Your organization has 200 microservices, 50 developers, and is experiencing:
- Mean Time to Detect (MTTD): 15 minutes
- Mean Time to Resolve (MTTR): 2 hours
- Goal: MTTD < 2 minutes, MTTR < 15 minutes

### Q1: What's your three-pillar observability architecture?

```
THE THREE PILLARS + CONTEXT:

┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY PLATFORM                         │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐            │
│  │   METRICS   │  │    LOGS     │  │   TRACES     │            │
│  │  (Numbers)  │  │  (Events)   │  │  (Journeys)  │            │
│  │             │  │             │  │              │            │
│  │ Prometheus  │  │ Loki/ELK   │  │ Tempo/Jaeger │            │
│  │ + Grafana   │  │ + Grafana   │  │ + Grafana    │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘            │
│         │                 │                 │                     │
│         └─────────────────┼─────────────────┘                    │
│                           │                                       │
│                    ┌──────▼──────┐                                │
│                    │ CORRELATION │  ← The MAGIC is here           │
│                    │ TraceID →   │  Connect metrics spike          │
│                    │ Logs →      │  to specific traces             │
│                    │ Traces      │  to specific log lines          │
│                    └─────────────┘                                │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ FOURTH PILLAR: PROFILING (continuous)                        ││
│  │ - async-profiler / Pyroscope for flame graphs               ││
│  │ - CPU, memory allocation, lock contention                   ││
│  │ - Correlate with traces: "why is this span slow?"           ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Q2: How do you implement distributed tracing in Spring Boot?

```java
// Spring Boot 3.x with Micrometer Tracing (replaces Spring Cloud Sleuth)

// 1. Dependencies
// spring-boot-starter-actuator
// micrometer-tracing-bridge-otel (OpenTelemetry bridge)
// opentelemetry-exporter-otlp (export to collector)

// 2. Configuration
// application.yml
management:
  tracing:
    sampling:
      probability: 0.1  # Sample 10% in production
  otlp:
    tracing:
      endpoint: http://otel-collector:4318/v1/traces

// 3. Automatic instrumentation (zero code change):
// - HTTP incoming (WebMVC/WebFlux)
// - HTTP outgoing (WebClient, RestClient)
// - JDBC queries
// - Kafka producer/consumer
// - Redis operations
// - Spring @Scheduled methods

// 4. Custom spans for business logic
@Service
public class OrderService {
    private final ObservationRegistry observationRegistry;

    public Order processOrder(OrderRequest request) {
        return Observation.createNotStarted("order.process", observationRegistry)
            .contextualName("process-order")
            .lowCardinalityKeyValue("order.type", request.getType())
            .highCardinalityKeyValue("order.id", request.getId())
            .observe(() -> {
                // Automatic span creation with timing
                Order order = createOrder(request);
                processPayment(order);
                reserveInventory(order);
                return order;
            });
    }
}

// 5. Propagation across async boundaries
@KafkaListener(topics = "orders")
public void handleOrder(
    @Payload OrderEvent event,
    @Header(KafkaHeaders.RECEIVED_TOPIC) String topic,
    Observation.Context context) {
    // Trace context automatically propagated via Kafka headers
    // Parent span from producer is linked
}
```

### Q3: How do you handle trace sampling at 500K rps?

```
Sampling Strategies:

1. PROBABILISTIC (simple, uniform)
   - Sample 1% of requests uniformly
   - Pro: Simple, predictable cost
   - Con: May miss rare errors

2. RATE-LIMITED (budget-based)
   - Sample max 100 traces/second per service
   - Pro: Predictable cost regardless of traffic
   - Con: Under-samples during spikes

3. ADAPTIVE / TAIL-BASED (intelligent)
   - Collect ALL traces initially
   - At collector: decide which to KEEP based on:
     * Error occurred → always keep
     * Latency > p99 → always keep
     * Specific user/tenant → always keep
     * Normal request → sample at 0.1%
   - Pro: Never miss interesting traces
   - Con: Collector must buffer, higher cost

4. HEAD-BASED + ERROR CAPTURE (pragmatic)
   - Sample 1% probabilistically
   - ALWAYS trace requests that result in errors
   - ALWAYS trace requests above latency threshold
   
   Implementation:
   @Bean
   public Sampler customSampler() {
       return new Sampler() {
           @Override
           public SamplingResult shouldSample(Context context, String traceId, 
                   String name, SpanKind kind, Attributes attributes) {
               // Always sample errors (determined later, use recordAndSample)
               // Sample 1% of normal traffic
               if (isHighPriorityTrace(attributes)) {
                   return SamplingResult.recordAndSample();
               }
               return Math.random() < 0.01 
                   ? SamplingResult.recordAndSample() 
                   : SamplingResult.drop();
           }
       };
   }

Cost Model at 500K rps:
  100% sampling: 500K spans/sec × 1KB × 86400s = 43TB/day ($$$$)
  1% sampling:   5K spans/sec × 1KB × 86400s = 430GB/day ($$)
  Tail-based:    ~2-5% effective × budget = $$
```

---

## Problem 2: Define SLOs/SLIs for a Spring Boot Platform

**Scenario:** You need to define SLOs for your platform team's services:
- API Gateway (routes all traffic)
- Authentication Service
- Core Business API
- Event Processing Pipeline

### Q4: How do you define meaningful SLIs and SLOs?

```
SLI (Service Level Indicator) - What we measure
SLO (Service Level Objective) - Target for the SLI
SLA (Service Level Agreement) - Business commitment (with consequences)

SLI TYPES:

1. AVAILABILITY:
   SLI = successful_requests / total_requests
   Measured at: Load balancer (most accurate, counts server errors)
   Exclude: Client errors (4xx are not availability failures)
   
   Formula: (total_requests - 5xx_requests) / total_requests

2. LATENCY:
   SLI = proportion of requests faster than threshold
   Example: 99% of requests < 200ms, 99.9% < 1000ms
   Measured at: Service-side (from request received to response sent)
   
   Use HISTOGRAM, not averages!

3. CORRECTNESS:
   SLI = correct_responses / total_responses
   Hard to measure automatically
   Use: checksums, verification queries, synthetic monitoring

4. FRESHNESS (for data pipelines):
   SLI = proportion of data processed within X seconds
   Example: 99% of events processed within 5 seconds

PER-SERVICE SLOs:

┌──────────────────┬────────────────┬───────────────────────┬──────────┐
│ Service          │ Availability   │ Latency              │ Error    │
│                  │ SLO            │ SLO                  │ Budget   │
├──────────────────┼────────────────┼───────────────────────┼──────────┤
│ API Gateway      │ 99.99%         │ p50<10ms, p99<50ms   │ 4.3min/mo│
│ Auth Service     │ 99.99%         │ p50<20ms, p99<100ms  │ 4.3min/mo│
│ Core Business API│ 99.95%         │ p50<100ms, p99<500ms │ 21.6min/mo│
│ Event Pipeline   │ 99.9%          │ 99% within 5sec      │ 43.8min/mo│
└──────────────────┴────────────────┴───────────────────────┴──────────┘

Error Budget = 1 - SLO
  99.99% → 0.01% error budget → 4.3 min downtime/month
  99.95% → 0.05% error budget → 21.6 min downtime/month
  99.9%  → 0.1% error budget  → 43.8 min downtime/month
```

### Q5: How do you implement SLO monitoring in Spring Boot?

```java
// Micrometer + Prometheus + Grafana SLO monitoring

@Configuration
public class SloMetricsConfig {
    
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> sloMetrics() {
        return registry -> {
            // Define SLO buckets for latency histogram
            // These align with your SLO thresholds
        };
    }
}

// Custom SLO tracking filter
@Component
public class SloTrackingFilter implements WebFilter {
    private final MeterRegistry registry;
    private final Timer requestTimer;
    private final Counter sloViolationCounter;
    
    public SloTrackingFilter(MeterRegistry registry) {
        this.registry = registry;
        this.requestTimer = Timer.builder("http.server.requests.slo")
            .publishPercentileHistogram()
            .serviceLevelObjectives(
                Duration.ofMillis(50),   // p50 SLO
                Duration.ofMillis(200),  // p95 SLO
                Duration.ofMillis(500)   // p99 SLO
            )
            .register(registry);
        this.sloViolationCounter = Counter.builder("slo.violations")
            .tag("type", "latency")
            .register(registry);
    }
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        long start = System.nanoTime();
        return chain.filter(exchange)
            .doFinally(signal -> {
                long duration = System.nanoTime() - start;
                requestTimer.record(duration, TimeUnit.NANOSECONDS);
                if (duration > 500_000_000) { // > 500ms
                    sloViolationCounter.increment();
                }
            });
    }
}

// Prometheus recording rules for SLO burn rate:
// groups:
// - name: slo-rules
//   rules:
//   - record: slo:api_availability:ratio_rate5m
//     expr: |
//       1 - (
//         sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
//         /
//         sum(rate(http_server_requests_seconds_count[5m]))
//       )
//
//   - alert: SLOBurnRateHigh
//     expr: slo:api_availability:ratio_rate5m < 0.999  # 99.9% in 5m window
//     for: 2m
//     labels:
//       severity: critical
```

---

## Problem 3: Build a Centralized Logging Architecture

**Scenario:** 200 services generate 5TB of logs/day. Current problems:
- No correlation across services
- Searching logs takes minutes
- Sensitive data leaking into logs
- Log storage costs are out of control

### Q6: How do you design the logging architecture?

```
ARCHITECTURE:

┌──────────────────────────────────────────────────────────────┐
│  Service (Spring Boot)                                        │
│  ├── Structured JSON logging (Logback + LogstashEncoder)     │
│  ├── TraceID/SpanID in every log line (MDC)                  │
│  ├── Sensitive data masking (custom encoder)                 │
│  └── Log level: INFO in prod, DEBUG via dynamic control      │
└───────────────────────┬──────────────────────────────────────┘
                        │ stdout (container logs)
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  Log Collector (Fluentd/Vector/Filebeat per node)            │
│  ├── Buffer locally (handle backpressure)                    │
│  ├── Parse & enrich (add K8s metadata: pod, namespace)       │
│  ├── Sample verbose logs (DEBUG at 1%, INFO at 100%)         │
│  ├── Route by level/service (hot/warm/cold tiers)            │
│  └── Forward to central                                       │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  Central Pipeline (Kafka)                                     │
│  ├── Buffer for spikes (retain 24h)                          │
│  ├── Multiple consumers for different destinations           │
│  └── Replay capability for reprocessing                      │
└───────┬──────────────────────────┬───────────────────────────┘
        │                          │
        ▼                          ▼
┌───────────────────┐    ┌────────────────────┐
│  Hot Storage      │    │  Cold Storage       │
│  (Loki/ES)        │    │  (S3 + Athena)      │
│  Last 7 days      │    │  Archived >7 days   │
│  Fast search      │    │  Cheap, slow query  │
│  Alerts trigger   │    │  Compliance/audit   │
└───────────────────┘    └────────────────────┘

Cost Optimization:
  5TB/day raw → After sampling/filtering: 1TB/day stored
  Hot (7 days): 7TB × $0.10/GB = $700/month
  Cold (90 days): 90TB × $0.023/GB = $2,070/month
  Total: ~$2,770/month (vs $35,000 if storing everything hot)
```

### Q7: How do you implement structured logging in Spring Boot?

```java
// logback-spring.xml
<configuration>
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>spanId</includeMdcKeyName>
            <includeMdcKeyName>userId</includeMdcKeyName>
            <includeMdcKeyName>requestId</includeMdcKeyName>
            
            <!-- Mask sensitive fields -->
            <jsonGeneratorDecorator class="com.example.SensitiveDataMaskingDecorator"/>
            
            <!-- Add service metadata -->
            <customFields>
                {"service":"${SERVICE_NAME}","env":"${ENVIRONMENT}"}
            </customFields>
        </encoder>
    </appender>
</configuration>

// Sensitive data masking
public class SensitiveDataMaskingDecorator implements JsonGeneratorDecorator {
    private static final Set<String> SENSITIVE_FIELDS = Set.of(
        "password", "ssn", "creditCard", "token", "secret"
    );
    
    @Override
    public JsonGenerator decorate(JsonGenerator generator) {
        return new MaskingJsonGenerator(generator, SENSITIVE_FIELDS);
    }
}

// Log output (JSON):
{
  "@timestamp": "2024-03-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "com.example.OrderService",
  "message": "Order created successfully",
  "traceId": "abc123def456",
  "spanId": "span789",
  "userId": "user-42",
  "service": "order-service",
  "env": "production",
  "order_id": "ORD-12345",
  "amount": 99.99,
  "duration_ms": 145
}

// Dynamic log level change (without restart)
@RestController
@RequestMapping("/admin/logging")
public class LoggingController {
    
    @PostMapping("/level")
    public void changeLogLevel(@RequestParam String logger, @RequestParam String level) {
        LoggerContext context = (LoggerContext) LoggerFactory.getILoggerFactory();
        context.getLogger(logger).setLevel(Level.valueOf(level));
    }
}
// Also available via Actuator: POST /actuator/loggers/{name}
```

---

## Problem 4: Design Alerting That Doesn't Cause Alert Fatigue

**Scenario:** Current state:
- 500 alerts/day, 80% are noise
- On-call engineers ignore alerts
- Real incidents buried in noise
- Alert storms during deployments

### Q8: How do you design an effective alerting strategy?

```
ALERTING PHILOSOPHY:
  Every alert must be ACTIONABLE
  If you can't define what to DO when the alert fires → delete it

ALERT HIERARCHY:

┌───────────────────────────────────────────────────────────────┐
│  TIER 1: PAGE (wake someone up)                               │
│  - SLO burn rate critical (will breach SLO within 1 hour)     │
│  - Service completely down (zero successful requests)         │
│  - Data loss risk (replication lag > threshold)               │
│  Target: <5 per week                                          │
├───────────────────────────────────────────────────────────────┤
│  TIER 2: TICKET (fix during business hours)                   │
│  - SLO burn rate elevated (will breach within 24 hours)       │
│  - Degraded performance (but within SLO)                      │
│  - Disk/memory approaching limits (>80%)                      │
│  Target: <20 per week                                         │
├───────────────────────────────────────────────────────────────┤
│  TIER 3: LOG/DASHBOARD (informational)                        │
│  - Retries increasing                                         │
│  - Error rate slightly elevated                               │
│  - Deployment happened                                        │
│  Target: Dashboard only, no notifications                     │
└───────────────────────────────────────────────────────────────┘

MULTI-WINDOW, MULTI-BURN-RATE ALERTING:

SLO: 99.9% availability (43.8 min error budget/month)

Alert Rules (burn rate based):
  - 14.4x burn rate for 1 hour → PAGE (uses budget in 5 hours)
  - 6x burn rate for 6 hours → PAGE (uses budget in 5 days)
  - 3x burn rate for 3 days → TICKET (uses budget in 10 days)
  - 1x burn rate for 7 days → TICKET (approaching budget)

Spring Boot Implementation:
  // Expose burn rate as a metric
  @Scheduled(fixedRate = 60000)
  public void calculateBurnRate() {
      double errorRate5m = getErrorRate(Duration.ofMinutes(5));
      double errorRate1h = getErrorRate(Duration.ofHours(1));
      double budget = 0.001; // 0.1% for 99.9% SLO
      
      double burnRate5m = errorRate5m / budget;
      double burnRate1h = errorRate1h / budget;
      
      registry.gauge("slo.burn_rate.5m", burnRate5m);
      registry.gauge("slo.burn_rate.1h", burnRate1h);
  }
```

### Q9: How do you prevent alert storms during deployments?

```
DEPLOYMENT-AWARE ALERTING:

1. Deployment Annotations:
   - Mark deployment start/end in monitoring system
   - Suppress non-critical alerts during deployment window
   - Auto-extend suppression if rollback detected

2. Canary-Based Alerting:
   - During canary: only alert if canary metrics deviate from baseline
   - After full rollout: resume normal alerting after soak period
   
   Implementation:
   @EventListener(DeploymentEvent.class)
   public void onDeployment(DeploymentEvent event) {
       if (event.getPhase() == STARTED) {
           alertingService.suppressNonCritical(event.getService(), Duration.ofMinutes(10));
       } else if (event.getPhase() == COMPLETED) {
           alertingService.resumeAfterSoak(event.getService(), Duration.ofMinutes(5));
       }
   }

3. Dependent Alert Suppression:
   - If database is DOWN → suppress all "service error" alerts (they're all DB-caused)
   - Root cause alert only: "Database unreachable"
   - Implement dependency graph: downstream alerts auto-suppressed

4. Alert Grouping & Deduplication:
   - Group alerts by root cause (same error across services)
   - One notification: "5 services affected by Database-Primary failure"
   - Not 50 individual "connection timeout" alerts
```

---

## Problem 5: Implement Production Debugging Without Disruption

**Scenario:** A service has intermittent latency spikes (p99 goes from 50ms to 5000ms for ~30 seconds). Need to debug without:
- Adding overhead in steady-state
- Restarting the service
- Affecting other requests

### Q10: What's your debugging toolkit and approach?

```
LIVE DEBUGGING TOOLKIT:

1. CONTINUOUS PROFILING (always on, low overhead):
   - async-profiler with 1% sampling → flame graphs
   - Allocation profiler → memory hotspots
   - Lock profiling → contention detection
   
   // Spring Boot integration via Pyroscope
   @Bean
   public PyroscopeAgent pyroscopeAgent() {
       return new PyroscopeAgent(Config.builder()
           .setServerAddress("http://pyroscope:4040")
           .setApplicationName("order-service")
           .setProfilingEnabled(true)
           .setSamplingRate(100) // 100Hz, ~1% overhead
           .build());
   }

2. DYNAMIC LOG LEVEL (on-demand verbosity):
   POST /actuator/loggers/com.example.OrderService
   {"configuredLevel": "DEBUG"}
   
   // Auto-revert after timeout:
   @Scheduled(fixedRate = 300000)
   public void revertDebugLogging() {
       dynamicLoggers.revertExpired();
   }

3. THREAD DUMP ON-DEMAND:
   GET /actuator/threaddump
   // Automated: capture thread dump when latency spike detected
   @Scheduled(fixedRate = 5000)
   public void monitorLatency() {
       if (currentP99 > threshold) {
           captureAndUploadThreadDump();
           captureAndUploadHeapHistogram();
       }
   }

4. MICROMETER OBSERVATIONS (business-level spans):
   // Already in code, zero-cost when not sampling
   // Increase sampling dynamically during investigation

5. CONDITIONAL TRACING:
   // Force-trace specific problematic requests
   GET /api/orders/123
   Header: X-Force-Trace: true
   // Always capture this trace regardless of sampling rate

6. JFR (Java Flight Recorder) events:
   // Low overhead, always-on event recording
   // Retrieve via: jcmd <pid> JFR.dump filename=recording.jfr
   // Or expose via Actuator endpoint
```

---

## Problem 6: Observability for Reactive / WebFlux Applications

### Q11: What's different about observing reactive applications?

```
CHALLENGES:
  1. No thread-per-request → ThreadLocal (MDC) doesn't work
  2. Stack traces are useless (all show event loop, no business context)
  3. Latency is harder to measure (multiple async hops)
  4. Context propagation across reactive operators

SOLUTIONS:

1. Context Propagation (Micrometer Context Propagation):
   // Automatically propagates TraceContext through Reactor context
   // Spring Boot 3.x does this automatically with micrometer-context-propagation
   
   Hooks.onEachOperator(Operators.lift(
       (scannable, subscriber) -> new ContextPropagatingSubscriber<>(subscriber)
   ));

2. MDC in Reactive (Reactor Context → MDC):
   @Bean
   public ContextSnapshotFactory contextSnapshotFactory() {
       return ContextSnapshotFactory.builder()
           .clearMissing(true)
           .build();
   }
   // Now MDC values propagate through Mono/Flux chains

3. Custom Observations for Reactive Chains:
   public Mono<Order> processOrder(OrderRequest request) {
       return Mono.deferContextual(ctx -> {
           Observation obs = Observation.start("order.process", registry);
           return createOrder(request)
               .flatMap(this::processPayment)
               .flatMap(this::reserveInventory)
               .doOnSuccess(order -> obs.stop())
               .doOnError(e -> {
                   obs.error(e);
                   obs.stop();
               });
       });
   }

4. Reactor Debug Agent (for readable stack traces):
   // In development/staging only (has overhead):
   ReactorDebugAgent.init();
   // Transforms async stack traces into readable format
   
   // Production alternative: checkpoint() at critical points:
   return webClient.get().uri("/api/users")
       .retrieve()
       .bodyToMono(User.class)
       .checkpoint("after-user-fetch")  // Appears in stack traces
       .flatMap(this::processUser)
       .checkpoint("after-process-user");

5. Subscription Tracing:
   // Track where subscriptions happen (who subscribed to what)
   Flux.just(1, 2, 3)
       .name("my-flux")          // Name for metrics
       .metrics()                // Auto-record throughput, errors
       .subscribe();
```

---

## Problem 7: Incident Response Automation

### Q12: How would you build an automated incident response system?

```
AUTOMATED INCIDENT LIFECYCLE:

Detection (< 1 min):
  ┌───────────────────────────────────────┐
  │ Prometheus Alert fires (SLO burn rate) │
  └────────────────┬──────────────────────┘
                   │
Triage (automated, < 30 sec):
  ┌────────────────▼──────────────────────┐
  │ Incident Classifier:                   │
  │ - Check dependent services health     │
  │ - Check recent deployments            │
  │ - Check infrastructure changes        │
  │ - Check similar past incidents        │
  │ Output: Probable cause + severity     │
  └────────────────┬──────────────────────┘
                   │
Notification (< 1 min):
  ┌────────────────▼──────────────────────┐
  │ Alert Router:                          │
  │ - Severity → correct on-call team     │
  │ - Create incident channel (Slack)     │
  │ - Populate with context:              │
  │   * Grafana dashboard links           │
  │   * Relevant trace examples           │
  │   * Recent deployments list           │
  │   * Suggested runbooks                │
  └────────────────┬──────────────────────┘
                   │
Mitigation (automated or guided):
  ┌────────────────▼──────────────────────┐
  │ Auto-Remediation (if confidence high): │
  │ - Rollback last deployment            │
  │ - Scale up instances                  │
  │ - Enable circuit breaker              │
  │ - Redirect traffic to healthy region  │
  └───────────────────────────────────────┘

Spring Boot Integration:
  @Component
  public class IncidentAutoRemediator {
      
      @EventListener(AlertFiredEvent.class)
      public void onAlert(AlertFiredEvent event) {
          if (event.getType() == DEPLOYMENT_RELATED) {
              DeploymentInfo lastDeploy = getLastDeployment(event.getService());
              if (lastDeploy.wasWithin(Duration.ofMinutes(30))) {
                  // Auto-rollback with notification
                  deploymentService.rollback(lastDeploy);
                  slackService.notify(event.getChannel(), 
                      "Auto-rolled back deployment " + lastDeploy.getVersion());
              }
          }
      }
  }
```

---

## Problem 8: Cost-Effective Observability at Scale

### Q13: How do you manage observability costs for 5TB of metrics + 5TB logs/day?

```
COST OPTIMIZATION STRATEGIES:

1. METRIC CARDINALITY MANAGEMENT:
   Problem: High cardinality labels explode storage
   Example: user_id as a label → 10M unique time series!
   
   Rules:
   - LOW cardinality labels only (service, endpoint, status, region)
   - NEVER: user_id, request_id, session_id as metric labels
   - Use logs/traces for high-cardinality data
   
   Spring Boot:
   @Bean
   public MeterFilter cardinalityFilter() {
       return MeterFilter.maximumAllowableMetrics(10000);
       // Also: deny specific high-cardinality meters
   }

2. METRIC AGGREGATION:
   - Raw metrics: 15s resolution, keep 24h
   - Aggregated: 1m resolution, keep 7d
   - Downsampled: 5m resolution, keep 30d
   - Summary: 1h resolution, keep 1yr
   
   Storage: 15s × 24h = 5,760 points → 1h × 1yr = 8,760 points
   400x reduction in long-term storage

3. LOG TIERING:
   - ERROR logs: always retain (30 days hot, 1 year cold)
   - INFO logs: retain 7 days hot
   - DEBUG logs: retain 24 hours (only if explicitly enabled)
   - Access logs: retain 7 days, sample at 10% after peak
   
   Dynamic sampling:
   if (currentLogRate > 10000/sec) {
       // Switch to sampling mode for INFO logs
       sampleRate = max(0.1, 10000.0 / currentRate);
   }

4. TRACE SAMPLING (cost vs insight trade-off):
   100% sampling = 10x cost
   1% sampling = miss rare events
   Tail-based = 3-5% cost, catch all errors
   
5. RETENTION POLICIES:
   Define per data type, per team, per service criticality
   
   Critical services: 30 day traces, 90 day metrics
   Non-critical: 7 day traces, 30 day metrics
   
   Monthly cost target per service: $50-200
   Total platform: $15K-40K/month for 200 services
```
