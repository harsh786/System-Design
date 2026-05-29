# Memory & CPU Issues - Diagnosis and Solutions

## Table of Contents
- [Memory Leaks](#memory-leaks)
- [OutOfMemoryError Types](#outofmemoryerror-types)
- [GC Tuning](#gc-tuning)
- [CPU Issues](#cpu-issues)
- [Thread Dumps Analysis](#thread-dumps-analysis)
- [Heap Dump Analysis](#heap-dump-analysis)
- [JVM Tuning for Spring Boot](#jvm-tuning-for-spring-boot)
- [Container Memory Management](#container-memory-management)

---

## Memory Leaks

### Q1: Common memory leaks in Spring Boot applications

**Answer:**

```java
// LEAK 1: ThreadLocal not cleaned up
@Component
public class RequestContextHolder {
    private static final ThreadLocal<RequestContext> context = new ThreadLocal<>();
    
    public void setContext(RequestContext ctx) {
        context.set(ctx);
    }
    
    // BUG: If request processing throws exception, cleanup never happens
    // In thread pool: thread is reused, old context leaks
    public void clear() {
        context.remove(); // MUST be called in finally block!
    }
}

// FIX: Use try-finally or Filter
@Component
public class RequestContextFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
        try {
            RequestContextHolder.setContext(new RequestContext(request));
            chain.doFilter(request, response);
        } finally {
            RequestContextHolder.clear(); // ALWAYS clean up
        }
    }
}

// LEAK 2: Event listeners holding references
@Component
public class LeakyListener implements ApplicationListener<ContextRefreshedEvent> {
    private final List<LargeObject> cache = new ArrayList<>(); // Grows forever!
    
    @Override
    public void onApplicationEvent(ContextRefreshedEvent event) {
        cache.add(loadLargeObject()); // Never evicted!
    }
}

// LEAK 3: Unclosed resources
@Service
public class DataProcessor {
    public void processFile(String path) {
        InputStream is = new FileInputStream(path); // Never closed on exception!
        // If exception thrown here, stream leaks
        process(is);
        is.close();
    }
    
    // FIX: try-with-resources
    public void processFileSafe(String path) {
        try (InputStream is = new FileInputStream(path)) {
            process(is);
        } // Auto-closed, even on exception
    }
}

// LEAK 4: Hibernate Session/EntityManager leak
@Service
public class UserService {
    @PersistenceContext
    private EntityManager entityManager;
    
    // BUG: Loading all entities into persistence context
    public void processAllUsers() {
        List<User> users = entityManager.createQuery("SELECT u FROM User u", User.class)
            .getResultList(); // Loads ALL users into memory!
        // Plus: all entities tracked by persistence context (dirty checking)
    }
    
    // FIX: Use pagination + clear
    public void processAllUsersSafe() {
        int page = 0;
        int size = 100;
        List<User> batch;
        do {
            batch = entityManager.createQuery("SELECT u FROM User u", User.class)
                .setFirstResult(page * size)
                .setMaxResults(size)
                .getResultList();
            
            batch.forEach(this::processUser);
            entityManager.clear(); // Release tracked entities from persistence context!
            page++;
        } while (batch.size() == size);
    }
}

// LEAK 5: String concatenation in loops (creates garbage)
public String buildReport(List<Record> records) {
    String result = ""; // New String object EVERY iteration!
    for (Record r : records) {
        result += r.toString(); // Creates intermediate String objects
    }
    return result;
}
// FIX: Use StringBuilder
public String buildReportFixed(List<Record> records) {
    StringBuilder sb = new StringBuilder(records.size() * 50); // Pre-size
    for (Record r : records) {
        sb.append(r.toString());
    }
    return sb.toString();
}

// LEAK 6: Class loader leak (common with hot-reload)
// Problem: Old classloader kept alive because something references its classes
// Symptoms: PermGen/Metaspace grows with each redeploy
// Solution: Ensure no references from parent classloader to child classloader objects

// LEAK 7: WebClient/HttpClient connection leak
@Service
public class ApiClient {
    public Mono<Data> fetchData() {
        return webClient.get()
            .uri("/api/data")
            .retrieve()
            .bodyToMono(Data.class);
        // If you use .exchange() instead of .retrieve(), 
        // you MUST consume or release the body!
    }
    
    // BUG with .exchange() (deprecated for this reason)
    public Mono<Data> fetchDataLeaky() {
        return webClient.get()
            .uri("/api/data")
            .exchangeToMono(response -> {
                if (response.statusCode().is2xxSuccessful()) {
                    return response.bodyToMono(Data.class);
                }
                // BUG: On non-2xx, body is NOT consumed → connection leak!
                return Mono.error(new RuntimeException("Failed"));
            });
    }
    
    // FIX: Always consume body
    public Mono<Data> fetchDataFixed() {
        return webClient.get()
            .uri("/api/data")
            .exchangeToMono(response -> {
                if (response.statusCode().is2xxSuccessful()) {
                    return response.bodyToMono(Data.class);
                }
                return response.bodyToMono(String.class) // Consume body!
                    .flatMap(body -> Mono.error(new RuntimeException("Failed: " + body)));
            });
    }
}
```

---

## OutOfMemoryError Types

### Q2: Different types of OOM and their causes

```
1. java.lang.OutOfMemoryError: Java heap space
   Cause: Heap is full, GC can't free enough memory
   Common reasons:
     - Memory leak (objects not being GC'd)
     - Processing too much data at once
     - Large collections growing unbounded
     - Heap too small for workload
   
   Fix: Increase -Xmx, find leak with heap dump

2. java.lang.OutOfMemoryError: Metaspace
   Cause: Class metadata area is full
   Common reasons:
     - Too many classes loaded (large dependency tree)
     - ClassLoader leak (hot deploy issues)
     - Heavy use of dynamic proxies/reflection
   
   Fix: Increase -XX:MaxMetaspaceSize, fix classloader leaks

3. java.lang.OutOfMemoryError: GC Overhead limit exceeded
   Cause: GC spending >98% time collecting <2% heap
   Means: You have a memory issue, GC is struggling
   
   Fix: Same as heap space OOM

4. java.lang.OutOfMemoryError: Direct buffer memory
   Cause: NIO direct buffers exhausted (off-heap)
   Common in: Netty, WebFlux, file I/O
   
   Fix: Increase -XX:MaxDirectMemorySize, ensure buffers released

5. java.lang.OutOfMemoryError: unable to create native thread
   Cause: OS limit on threads reached
   Common reasons:
     - Thread pool not bounded
     - Too many threads per process
     - OS ulimit too low
   
   Fix: ulimit -u increase, bound thread pools, use virtual threads

6. java.lang.OutOfMemoryError: Requested array size exceeds VM limit
   Cause: Trying to allocate array larger than Integer.MAX_VALUE
   
   Fix: Process data in chunks
```

```java
// Diagnosing OOM: JVM flags for production
// -XX:+HeapDumpOnOutOfMemoryError
// -XX:HeapDumpPath=/var/dumps/heap.hprof
// -XX:+ExitOnOutOfMemoryError (or CrashOnOutOfMemoryError)

// Spring Boot application configuration
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}

// JVM arguments (in Dockerfile or startup script):
// java -Xms512m -Xmx2g \
//      -XX:+HeapDumpOnOutOfMemoryError \
//      -XX:HeapDumpPath=/dumps/ \
//      -XX:+ExitOnOutOfMemoryError \
//      -XX:MaxMetaspaceSize=256m \
//      -XX:MaxDirectMemorySize=512m \
//      -jar app.jar
```

---

## GC Tuning

### Q3: How to choose and tune the right GC for Spring Boot?

```
GARBAGE COLLECTOR SELECTION:

┌─────────────────────┬──────────────────┬──────────────────────────────────┐
│ GC                  │ Best For         │ Characteristics                   │
├─────────────────────┼──────────────────┼──────────────────────────────────┤
│ G1GC (default)      │ General purpose  │ Balanced throughput/latency       │
│                     │ 4-64GB heap      │ Pause target: 200ms default       │
├─────────────────────┼──────────────────┼──────────────────────────────────┤
│ ZGC                 │ Low latency      │ Sub-ms pauses (< 1ms!)            │
│                     │ Large heaps      │ Good for: WebFlux, real-time      │
│                     │ (8MB - 16TB)     │ Slight throughput overhead         │
├─────────────────────┼──────────────────┼──────────────────────────────────┤
│ Shenandoah          │ Low latency      │ Similar to ZGC                    │
│                     │ (OpenJDK)        │ Concurrent compaction              │
├─────────────────────┼──────────────────┼──────────────────────────────────┤
│ Parallel GC         │ Throughput       │ Higher throughput, longer pauses   │
│                     │ Batch processing │ Good for: background jobs          │
├─────────────────────┼──────────────────┼──────────────────────────────────┤
│ Serial GC           │ Small heaps      │ Single-threaded, for < 100MB      │
│                     │ Containers       │ Low overhead, long pauses          │
└─────────────────────┴──────────────────┴──────────────────────────────────┘
```

```bash
# G1GC tuning (default in JDK 9+)
java -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=100 \        # Target pause time
     -XX:G1HeapRegionSize=16m \         # Region size (1-32MB, power of 2)
     -XX:InitiatingHeapOccupancyPercent=45 \ # Start concurrent GC at 45% heap
     -XX:G1NewSizePercent=20 \          # Min young gen
     -XX:G1MaxNewSizePercent=40 \       # Max young gen
     -Xms2g -Xmx2g \                   # Fixed heap (avoid resize overhead)
     -jar app.jar

# ZGC for low-latency (JDK 15+)
java -XX:+UseZGC \
     -XX:+ZGenerational \               # Generational ZGC (JDK 21+, better throughput)
     -Xms4g -Xmx4g \
     -jar app.jar

# GC logging (JDK 9+ unified logging)
java -Xlog:gc*=info:file=/var/log/gc.log:time,uptime,level,tags:filecount=10,filesize=50m \
     -jar app.jar
```

### Q4: How to analyze GC logs?

```
Key GC metrics to monitor:
  - GC pause time (p99, p95, max)
  - GC frequency (how often)
  - Allocation rate (MB/s of new objects)
  - Promotion rate (MB/s from young to old gen)
  - Heap after GC (residual live data)

Healthy GC:
  - Young GC: < 20ms, every 1-5 seconds
  - Old GC: < 200ms, rarely (every few minutes)
  - Heap after full GC: < 50% of max heap

Unhealthy GC (memory leak symptoms):
  - Heap after GC keeps GROWING over time
  - Full GC frequency increasing
  - Full GC not reclaiming much memory
  - GC pause times increasing

Tools:
  - GCViewer (analyze gc.log)
  - GCEasy (gceasy.io - upload gc.log)
  - JDK Mission Control (JFR)
  - Grafana + Prometheus (micrometer metrics)
```

```java
// Expose GC metrics via Micrometer
@Configuration
public class GcMetricsConfig {
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> gcMetrics() {
        return registry -> {
            new JvmGcMetrics().bindTo(registry);
            new JvmMemoryMetrics().bindTo(registry);
            new JvmThreadMetrics().bindTo(registry);
        };
    }
}

// Alert on GC pressure
// Prometheus alert rule:
// alert: HighGCTime
// expr: rate(jvm_gc_pause_seconds_sum[5m]) > 0.1  # >10% time in GC
// for: 5m
// labels:
//   severity: warning
```

---

## CPU Issues

### Q5: Common CPU-related issues in Spring Boot

```
HIGH CPU CAUSES:

1. INFINITE LOOPS / BUSY SPIN
   - Bug in code causing infinite loop
   - Busy-wait polling (Thread.yield() in a loop)
   - CAS retry loops under high contention (AtomicInteger)

2. EXCESSIVE GC (GC Overhead)
   - Memory leak causing constant Full GC
   - Heap too small → frequent collections
   - High allocation rate → frequent Young GC

3. THREAD CONTENTION
   - Many threads competing for same lock
   - synchronized on hot path
   - Single-threaded bottleneck (e.g., shared logger lock)

4. INEFFICIENT ALGORITHMS
   - O(n²) or O(n³) operations on large datasets
   - Recursive operations without memoization
   - Regex backtracking on user input

5. EXCESSIVE SERIALIZATION
   - Large object graphs serialized repeatedly
   - Jackson serializing huge objects
   - Redis/cache serialization overhead

6. REFLECTION OVERHEAD
   - Heavy use of reflection in hot paths
   - Spring AOP proxy overhead
   - Dynamic proxy creation
```

```java
// CPU ISSUE: Regex catastrophic backtracking
@Service
public class InputValidator {
    // DANGEROUS: This regex can take exponential time on crafted input!
    private static final Pattern EMAIL_PATTERN = 
        Pattern.compile("^([a-zA-Z0-9]+)*@([a-zA-Z0-9]+)*\\.com$");
    
    public boolean validateEmail(String email) {
        // Input: "aaaaaaaaaaaaaaaaaaaaaaaa!" → takes MINUTES
        return EMAIL_PATTERN.matcher(email).matches();
    }
    
    // FIX: Use possessive quantifiers or atomic groups
    private static final Pattern SAFE_EMAIL_PATTERN = 
        Pattern.compile("^[a-zA-Z0-9]++@[a-zA-Z0-9]++\\.com$");
}

// CPU ISSUE: N+1 query problem causing excessive DB calls
@Service
public class OrderService {
    public List<OrderDTO> getAllOrders() {
        List<Order> orders = orderRepo.findAll(); // 1 query
        return orders.stream()
            .map(order -> {
                List<Item> items = itemRepo.findByOrderId(order.getId()); // N queries!
                return new OrderDTO(order, items);
            })
            .collect(Collectors.toList());
    }
    
    // FIX: Use JOIN FETCH
    @Query("SELECT o FROM Order o JOIN FETCH o.items")
    List<Order> findAllWithItems(); // 1 query
}

// CPU ISSUE: Unnecessary object creation in hot path
@Service
public class MetricsService {
    public void recordMetric(String name, double value) {
        // Creates new SimpleDateFormat EVERY call (expensive!)
        String timestamp = new SimpleDateFormat("yyyy-MM-dd").format(new Date());
        log.info("{} {} {}", timestamp, name, value);
    }
    
    // FIX: Reuse formatter (thread-safe in Java 8+)
    private static final DateTimeFormatter FORMATTER = 
        DateTimeFormatter.ofPattern("yyyy-MM-dd");
    
    public void recordMetricFixed(String name, double value) {
        String timestamp = LocalDate.now().format(FORMATTER);
        log.info("{} {} {}", timestamp, name, value);
    }
}
```

### Q6: How to diagnose CPU issues in production?

```bash
# 1. Find the Java process
jps -l
# or: ps aux | grep java

# 2. Check which threads consume most CPU
top -H -p <PID>  # Shows per-thread CPU usage on Linux

# 3. Take thread dump
jstack <PID> > threaddump.txt
# Convert thread IDs (from top -H) from decimal to hex
# Match hex thread ID (nid) in thread dump

# 4. Continuous profiling (async-profiler)
# Download from https://github.com/async-profiler/async-profiler
./profiler.sh -d 30 -f flamegraph.html <PID>
# Generates flame graph showing where CPU time is spent

# 5. JFR (Java Flight Recorder) - production-safe
java -XX:StartFlightRecording=duration=60s,filename=recording.jfr \
     -jar app.jar
# Or attach to running process:
jcmd <PID> JFR.start duration=60s filename=recording.jfr
```

---

## Thread Dumps Analysis

### Q7: How to read and analyze thread dumps?

```
THREAD STATES:

NEW          - Thread created but not started
RUNNABLE     - Running or ready to run (may be doing I/O)
BLOCKED      - Waiting to acquire a monitor (synchronized)
WAITING      - Waiting indefinitely (wait(), join(), park())
TIMED_WAITING - Waiting with timeout (sleep(), wait(timeout))
TERMINATED   - Thread finished

WHAT TO LOOK FOR:

1. DEADLOCK (most critical):
   "Found one Java-level deadlock:"
   Thread-1 → waiting for lock held by Thread-2
   Thread-2 → waiting for lock held by Thread-1

2. THREAD POOL EXHAUSTION:
   All threads in WAITING/TIMED_WAITING
   Many threads "waiting on condition" (waiting for work from queue)
   If all threads BLOCKED on same lock → bottleneck

3. LOCK CONTENTION:
   Many threads BLOCKED waiting for same monitor
   "waiting to lock <0x...> (a java.util.HashMap)"
   → Use ConcurrentHashMap!

4. STUCK THREADS:
   Threads stuck in I/O operations for too long
   "java.net.SocketInputStream.read()" for minutes
   → Add timeouts!
```

```
EXAMPLE THREAD DUMP ANALYSIS:

"http-nio-8080-exec-1" #23 daemon prio=5 os_prio=0 tid=0x00007f... nid=0x1a BLOCKED
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.UserService.getUser(UserService.java:45)
        - waiting to lock <0x000000076bf8> (a com.example.UserCache)
        at com.example.UserController.getUser(UserController.java:30)

"http-nio-8080-exec-2" #24 daemon prio=5 os_prio=0 tid=0x00007f... nid=0x1b BLOCKED
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.UserService.getUser(UserService.java:45)
        - waiting to lock <0x000000076bf8> (a com.example.UserCache)

"http-nio-8080-exec-3" #25 daemon prio=5 os_prio=0 tid=0x00007f... nid=0x1c RUNNABLE
   java.lang.Thread.State: RUNNABLE
        at com.example.UserCache.loadFromDb(UserCache.java:78)
        - locked <0x000000076bf8> (a com.example.UserCache)  ← HOLDS THE LOCK
        at java.net.SocketInputStream.read(SocketInputStream.java:200)

DIAGNOSIS: Thread exec-3 holds lock on UserCache while doing DB I/O (slow!)
           Threads exec-1, exec-2 (and likely many more) are BLOCKED waiting
           
SOLUTION: Don't hold lock during I/O, or use ConcurrentHashMap.computeIfAbsent()
```

---

## Heap Dump Analysis

### Q8: How to capture and analyze heap dumps?

```bash
# Capture heap dump
# Method 1: jmap
jmap -dump:format=b,file=heap.hprof <PID>

# Method 2: JVM flag (on OOM)
java -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps/ -jar app.jar

# Method 3: jcmd (preferred - doesn't require tools.jar)
jcmd <PID> GC.heap_dump /tmp/heap.hprof

# Method 4: Spring Boot Actuator
# GET /actuator/heapdump → downloads heap dump

# Analyze with:
# - Eclipse MAT (Memory Analyzer Tool) - best for leak detection
# - VisualVM
# - JDK Mission Control
# - IntelliJ Profiler
```

**What to look for in heap dump:**

```
1. DOMINATOR TREE:
   Shows which objects "dominate" (retain) the most memory
   Top dominators are your biggest memory consumers
   
   Example:
   com.example.CacheManager → retains 1.2GB
     └── java.util.HashMap → retains 1.1GB
         └── 5,000,000 com.example.Product entries
   
   DIAGNOSIS: Cache growing unbounded!

2. HISTOGRAM (by class):
   Class                          | Instances | Shallow Size | Retained Size
   byte[]                         | 2,000,000 | 800MB        | 800MB
   java.lang.String               | 1,500,000 | 36MB         | 400MB
   com.example.Order              |   500,000 | 20MB         | 250MB
   
   Look for: Unexpectedly high instance counts

3. LEAK SUSPECTS (MAT auto-analysis):
   "com.example.EventListener holds 45% of heap"
   Shows GC root → path to leaked objects

4. GC ROOTS:
   Why objects can't be garbage collected:
   - Thread locals (ThreadLocal references)
   - Static fields
   - Active threads' stack frames
   - JNI references
```

---

## JVM Tuning for Spring Boot

### Q9: Production JVM configuration for Spring Boot

```bash
# RECOMMENDED JVM FLAGS FOR PRODUCTION

java \
  # Memory
  -Xms2g -Xmx2g \                          # Fixed heap (avoid resize)
  -XX:MaxMetaspaceSize=256m \               # Limit metaspace
  -XX:MaxDirectMemorySize=512m \            # For NIO buffers (Netty)
  
  # GC (choose one)
  -XX:+UseG1GC \                            # G1 for general
  -XX:MaxGCPauseMillis=100 \                # Target pause
  # OR for low latency:
  # -XX:+UseZGC -XX:+ZGenerational \
  
  # OOM handling
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/var/dumps/ \
  -XX:+ExitOnOutOfMemoryError \             # Restart on OOM (let K8s handle)
  
  # GC Logging
  -Xlog:gc*=info:file=/var/log/gc.log:time,uptime:filecount=5,filesize=50m \
  
  # JIT
  -XX:+TieredCompilation \                  # Faster startup
  -XX:ReservedCodeCacheSize=256m \          # JIT code cache
  
  # Thread
  -XX:ThreadStackSize=512k \                # Reduce thread stack (default 1MB)
  
  # Diagnostics
  -XX:+UnlockDiagnosticVMOptions \
  -XX:+DebugNonSafepoints \                 # Better profiling
  -XX:NativeMemoryTracking=summary \        # Track native memory
  
  # Container awareness (JDK 10+)
  -XX:+UseContainerSupport \                # Respect container limits
  -XX:MaxRAMPercentage=75.0 \              # Use 75% of container memory
  
  -jar app.jar
```

### Q10: Container-specific JVM tuning

```dockerfile
# Dockerfile for Spring Boot
FROM eclipse-temurin:21-jre-alpine

# Set container-aware JVM flags
ENV JAVA_OPTS="-XX:+UseContainerSupport \
  -XX:MaxRAMPercentage=75.0 \
  -XX:InitialRAMPercentage=50.0 \
  -XX:+UseG1GC \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/dumps/ \
  -XX:+ExitOnOutOfMemoryError"

COPY target/app.jar /app/app.jar

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]
```

```yaml
# Kubernetes resource limits
spec:
  containers:
    - name: app
      resources:
        requests:
          memory: "1Gi"    # Guaranteed memory
          cpu: "500m"      # 0.5 CPU
        limits:
          memory: "2Gi"    # Max memory (OOMKilled if exceeded)
          cpu: "2000m"     # Max 2 CPUs

# Memory calculation:
# Container limit: 2Gi
# JVM Heap (75%): 1.5GB (-XX:MaxRAMPercentage=75.0)
# Non-heap: ~300-500MB
#   - Metaspace: 256MB
#   - Thread stacks: 200 threads * 512KB = 100MB
#   - Direct buffers: configurable
#   - JIT code cache: 256MB
#   - GC overhead: varies
# Safety margin: ~200MB
```

---

## Container Memory Management

### Q11: Why do Spring Boot apps get OOMKilled in containers?

```
CONTAINER MEMORY = JVM Heap + Non-Heap + Native Memory

┌─────────────────────────────────────────────────────┐
│              Container Memory Limit (2GB)             │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  JVM Heap (-Xmx): 1.5GB                      │   │
│  │  (Objects, arrays, string pool)               │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Metaspace: ~150MB                            │   │
│  │  (Class metadata, method bytecode)            │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Thread Stacks: ~100MB                        │   │
│  │  (200 threads × 512KB each)                   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Direct Buffers: ~100MB                       │   │
│  │  (NIO, Netty buffers)                         │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Native Memory: ~50-100MB                     │   │
│  │  (JNI, JIT compiled code, GC structures)      │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Total: 1.5GB + 150MB + 100MB + 100MB + 100MB      │
│       = ~1.95GB (DANGEROUSLY close to 2GB limit!)   │
└─────────────────────────────────────────────────────┘
```

**Monitoring native memory:**
```bash
# Enable Native Memory Tracking
java -XX:NativeMemoryTracking=summary -jar app.jar

# Check at runtime
jcmd <PID> VM.native_memory summary

# Output:
# Total: reserved=3500MB, committed=2100MB
#   - Java Heap: reserved=1536MB, committed=1536MB
#   - Class: reserved=200MB, committed=150MB
#   - Thread: reserved=150MB, committed=150MB
#   - Code: reserved=256MB, committed=100MB
#   - GC: reserved=100MB, committed=80MB
#   - Internal: reserved=50MB, committed=30MB
#   - Symbol: reserved=20MB, committed=20MB
#   - Direct: reserved=100MB, committed=90MB
```

### Q12: Memory optimization techniques

```java
// 1. Use compact data structures
// Instead of Map<String, Object> for feature flags:
private final boolean[] flags = new boolean[100]; // Array vs HashMap

// 2. Object pooling for expensive objects
@Bean
public GenericObjectPool<ExpensiveResource> resourcePool() {
    GenericObjectPoolConfig<ExpensiveResource> config = new GenericObjectPoolConfig<>();
    config.setMaxTotal(20);
    config.setMaxIdle(10);
    config.setMinIdle(5);
    return new GenericObjectPool<>(new ExpensiveResourceFactory(), config);
}

// 3. Avoid autoboxing in hot paths
// BAD: Map<Integer, Long> creates Integer and Long objects for every entry
Map<Integer, Long> counts = new HashMap<>(); // Millions of boxed objects!

// GOOD: Use primitive collections (Eclipse Collections, Koloboke, etc.)
IntLongHashMap counts = new IntLongHashMap(); // No boxing!

// 4. String deduplication (for string-heavy apps)
// -XX:+UseStringDeduplication (G1GC only)
// Deduplicates char[] arrays of duplicate strings

// 5. Compressed OOPs (enabled by default for heap < 32GB)
// -XX:+UseCompressedOops (4-byte references instead of 8-byte)
// Breaks if heap > 32GB!

// 6. Off-heap storage for large datasets
// Use ByteBuffer.allocateDirect() or libraries like Chronicle Map
ChronicleMap<String, byte[]> offHeapCache = ChronicleMapBuilder
    .of(String.class, byte[].class)
    .entries(1_000_000)
    .averageKeySize(50)
    .averageValueSize(500)
    .createPersistedTo(new File("/tmp/cache.dat"));
```

---

## Profiling Tools

### Q13: What tools to use for memory/CPU profiling?

```
PRODUCTION-SAFE PROFILING:

1. async-profiler (RECOMMENDED for production)
   - Sampling profiler, <1% overhead
   - CPU, allocation, lock profiling
   - Generates flame graphs
   - Linux/macOS, attaches to running JVM

2. JDK Flight Recorder (JFR)
   - Built into JDK (free since JDK 11)
   - ~1% overhead
   - CPU, memory, I/O, locks, exceptions
   - Always-on profiling possible

3. Spring Boot Actuator + Micrometer
   - JVM metrics (heap, GC, threads)
   - Export to Prometheus/Grafana
   - No overhead for basic metrics

4. Arthas (Alibaba)
   - Attach to running JVM
   - Monitor method execution time
   - Watch method parameters/return values
   - Decompile classes at runtime

NOT PRODUCTION-SAFE:
- VisualVM (high overhead, requires JMX)
- YourKit (licensed, moderate overhead)
- JProfiler (licensed, moderate overhead)
- Use these in development/staging only
```

```bash
# async-profiler usage
# CPU profiling
./asprof -d 30 -f cpu.html <PID>

# Allocation profiling (find what's allocating memory)
./asprof -d 30 -e alloc -f alloc.html <PID>

# Lock profiling (find contention)
./asprof -d 30 -e lock -f lock.html <PID>

# Wall-clock profiling (includes I/O wait time)
./asprof -d 30 -e wall -f wall.html <PID>
```
