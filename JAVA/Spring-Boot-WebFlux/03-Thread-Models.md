# Thread Models - Thread-per-Request vs Event Loop

## Table of Contents
- [Thread-per-Request Model (Servlet)](#thread-per-request-model-servlet)
- [Event Loop Model (Netty/WebFlux)](#event-loop-model-nettywebflux)
- [Virtual Threads (Project Loom)](#virtual-threads-project-loom)
- [Comparison Matrix](#comparison-matrix)
- [When to Use What](#when-to-use-what)

---

## Thread-per-Request Model (Servlet)

### Q1: How does the traditional thread-per-request model work?

**Answer:**

```
┌─────────────────────────────────────────────────────────────┐
│              TOMCAT THREAD POOL (200 threads)                 │
│                                                              │
│  Incoming Request ──→ Acceptor Thread                        │
│                          │                                   │
│                          ▼                                   │
│                      Thread Pool                             │
│                   ┌──────────────┐                           │
│                   │ Thread-1 [BUSY] ─── Processing Req A     │
│                   │ Thread-2 [BUSY] ─── Processing Req B     │
│                   │ Thread-3 [IDLE]                          │
│                   │ Thread-4 [BUSY] ─── Waiting for DB       │
│                   │ ...                                      │
│                   │ Thread-200 [BUSY] ─ Waiting for HTTP     │
│                   └──────────────┘                           │
│                                                              │
│  Thread-4 timeline:                                          │
│  ─────[Parse Request]─[DB Query WAITING...]─[Build Response]─│
│       ← 1ms →          ← 50ms →              ← 1ms →        │
│                                                              │
│  Thread is BLOCKED for 50ms doing NOTHING!                   │
│  That's 98% waste of thread resources!                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Characteristics:**

| Property | Value |
|----------|-------|
| Thread per request | Yes |
| Max concurrent requests | = Thread pool size (default 200) |
| Memory per thread | ~1MB (stack size) |
| Memory for 200 threads | ~200MB just for stacks |
| Context switching | Heavy (OS-level) |
| ThreadLocal | Works perfectly |
| Debugging | Easy (stack trace shows full call chain) |
| Blocking I/O | Acceptable (thread just waits) |

### Q2: What happens when all threads are busy?

```
Scenario: 200 threads busy, 201st request arrives

┌──────────────────────────────────────────┐
│  Thread Pool: ALL 200 THREADS BUSY        │
│                                           │
│  New Request → Accept Queue (backlog)     │
│                ┌────────────────────┐     │
│                │ Req-201            │     │
│                │ Req-202            │     │
│                │ Req-203            │     │
│                │ ...                │     │
│                │ Req-300 (max=100)  │     │
│                └────────────────────┘     │
│                                           │
│  Req-301 → CONNECTION REFUSED!            │
│  (accept-count exceeded)                  │
└──────────────────────────────────────────┘

Timeline for Req-201 (queued):
  [─── Queuing (waiting for free thread) ───][── Processing ──]
  ← 0ms to several seconds →                 ← actual work →

Result: Latency SPIKES when threads exhausted
```

**Configuration:**
```yaml
server:
  tomcat:
    threads:
      max: 200         # Max worker threads
      min-spare: 10    # Min idle threads kept alive
    max-connections: 8192  # Max TCP connections (NIO handles)
    accept-count: 100      # Backlog queue when max-connections reached
    connection-timeout: 20000
```

### Q3: How does Tomcat's NIO improve the traditional model?

```
OLD Tomcat (BIO - Blocking I/O):
  1 Thread per CONNECTION (even idle HTTP keep-alive connections)
  200 threads = 200 connections MAX
  
NEW Tomcat (NIO - Non-blocking I/O, default since Tomcat 8):
  NIO Selector monitors all CONNECTIONS
  Thread only needed when data is READY to process
  
  ┌─────────────────────────────────────────────┐
  │  Acceptor Thread: Accepts connections        │
  │         ▼                                    │
  │  Poller Thread (NIO Selector):               │
  │    Monitors 8192 connections for readiness   │
  │    Only dispatches to worker when data ready │
  │         ▼                                    │
  │  Worker Threads (200): Process requests      │
  │    Still blocks during request processing    │
  │    But connections != threads                 │
  └─────────────────────────────────────────────┘
  
  8192 connections possible with only 200 worker threads!
  Idle keep-alive connections don't consume threads.
```

---

## Event Loop Model (Netty/WebFlux)

### Q4: How does the Event Loop model work in detail?

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│              NETTY EVENT LOOP (4 threads on 4-core machine)        │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  EventLoop Thread-1 (manages ~2500 connections)              │ │
│  │                                                               │ │
│  │  Execution Cycle (runs continuously):                         │ │
│  │  ┌──────────────────────────────────────────────────────┐    │ │
│  │  │ 1. selector.select() - which channels have I/O?      │    │ │
│  │  │    Channel-42: READ ready                             │    │ │
│  │  │    Channel-108: WRITE ready                           │    │ │
│  │  │                                                       │    │ │
│  │  │ 2. Process I/O events:                                │    │ │
│  │  │    Channel-42: Read HTTP request → decode → route     │    │ │
│  │  │      → Build reactive pipeline                        │    │ │
│  │  │      → Start async DB call (non-blocking)             │    │ │
│  │  │      → MOVE ON (don't wait!)                          │    │ │
│  │  │    Channel-108: Write response bytes to socket        │    │ │
│  │  │                                                       │    │ │
│  │  │ 3. Process task queue:                                │    │ │
│  │  │    - DB call for Channel-42 completed (callback)      │    │ │
│  │  │    - Build response, write to Channel-42              │    │ │
│  │  │    - Scheduled health check task                      │    │ │
│  │  └──────────────────────────────────────────────────────┘    │ │
│  │                                                               │ │
│  │  Total time per cycle: ~microseconds to low milliseconds      │ │
│  │  Handles thousands of requests without ANY blocking            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  EventLoop Thread-2: (same pattern, different connections)         │
│  EventLoop Thread-3: (same pattern, different connections)         │
│  EventLoop Thread-4: (same pattern, different connections)         │
└──────────────────────────────────────────────────────────────────┘
```

### Q5: How does a non-blocking DB call work step by step?

```
Timeline (Event Loop Thread-1):

Time 0μs:    Read HTTP request from Channel-42
Time 10μs:   Decode request, route to handler
Time 20μs:   Handler creates reactive pipeline
Time 30μs:   R2DBC: Send SQL query to DB (non-blocking write to DB socket)
             Register callback: "when response comes, execute this"
Time 35μs:   DONE with Channel-42 for now → process next channel
Time 40μs:   Process Channel-108 (different request)
Time 50μs:   Process Channel-203 (different request)
...
Time 5000μs: DB response arrives on DB connection socket
             Selector detects: DB channel readable
             Read DB response → execute registered callback
             Build HTTP response → write to Channel-42
Time 5010μs: Channel-42 response sent

Total thread busy time: ~50μs (NOT 5000μs!)
Thread was available for other work during 4950μs DB wait
```

### Q6: What are the key differences in resource usage?

```
Scenario: 10,000 concurrent requests, each with 100ms I/O wait

THREAD-PER-REQUEST (Tomcat):
  Threads needed: 10,000 (or queue with 200 threads)
  Memory for threads: 10,000 × 1MB = 10GB (impossible!)
  With 200 threads: 200 concurrent, 9800 queued
  Average latency: request_time + queue_time
  Context switches: massive (10000 threads competing for 4 CPUs)
  
EVENT LOOP (Netty):
  Threads needed: 4 (one per CPU core)
  Memory for threads: 4 × 1MB = 4MB
  Concurrent handling: ALL 10,000 simultaneously
  Average latency: ~request_time (minimal queuing)
  Context switches: minimal (only 4 threads)
  
  BUT: Each request's state is on HEAP (not stack)
  Memory for request state: 10,000 × ~10KB = ~100MB
  Still MUCH less than 10GB!
```

---

## Virtual Threads (Project Loom)

### Q7: How do Virtual Threads change the picture?

**Answer:**

Virtual Threads (Java 21+) are lightweight threads managed by the JVM, not the OS.

```
┌──────────────────────────────────────────────────────────────┐
│              VIRTUAL THREADS (Project Loom)                    │
│                                                               │
│  Platform Threads (OS threads): ~4-8 (carrier threads)        │
│  Virtual Threads: MILLIONS possible                           │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  ForkJoinPool (Carrier Threads)                       │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │    │
│  │  │Carrier-1 │ │Carrier-2 │ │Carrier-3 │             │    │
│  │  │          │ │          │ │          │             │    │
│  │  │ VT-1     │ │ VT-3     │ │ VT-5     │ (mounted)   │    │
│  │  │ VT-2*    │ │ VT-4*    │ │ VT-6*    │             │    │
│  │  └──────────┘ └──────────┘ └──────────┘             │    │
│  │                                                       │    │
│  │  * = VT yielded (blocked on I/O, unmounted)          │    │
│  │  Unmounted VTs: VT-7, VT-8, ... VT-10000            │    │
│  │  (stored as objects on heap, ~1KB each!)             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  When VT blocks on I/O:                                       │
│  1. VT is "unmounted" from carrier (saves continuation)       │
│  2. Carrier thread picks up another VT                        │
│  3. When I/O completes, VT is re-mounted on any carrier       │
└──────────────────────────────────────────────────────────────┘
```

**Spring Boot with Virtual Threads (Spring Boot 3.2+):**

```yaml
# application.yml
spring:
  threads:
    virtual:
      enabled: true  # That's it! Tomcat uses virtual threads
```

```java
// What this does internally:
@Bean
public TomcatProtocolHandlerCustomizer<?> protocolHandlerVirtualThreadExecutorCustomizer() {
    return protocolHandler -> {
        protocolHandler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
    };
}

// Now each request gets its own virtual thread
// Blocking is OK! The virtual thread yields, carrier is freed
@GetMapping("/users/{id}")
public User getUser(@PathVariable String id) {
    // This BLOCKS the virtual thread (which is fine!)
    // The carrier thread is freed for other virtual threads
    return jdbcTemplate.queryForObject("SELECT * FROM users WHERE id = ?", User.class, id);
}
```

### Q8: Virtual Threads vs WebFlux - which to choose?

| Aspect | Virtual Threads | WebFlux |
|--------|----------------|---------|
| Programming model | Imperative (blocking-style) | Reactive (Mono/Flux) |
| Learning curve | Low (write normal code) | High (reactive operators) |
| Blocking libs | Works great (JDBC, etc.) | Must avoid or wrap |
| Memory per request | ~1-5KB | ~1-10KB |
| Max concurrency | Millions | Millions |
| Debugging | Easy (stack traces) | Hard (async) |
| Backpressure | No built-in | Native support |
| Streaming | Thread-per-connection (SSE) | Native (Flux) |
| Ecosystem | Existing Java ecosystem | Reactive ecosystem needed |
| Best for | Request-response APIs | Streaming, event-driven |

**Recommendation:**
```
New project, Java 21+:
  - Request-response APIs → Virtual Threads (simpler code)
  - Streaming/events/high-fan-out → WebFlux (better fit)
  - Need backpressure → WebFlux
  
Existing project:
  - Already on WebFlux → Stay (unless struggling with complexity)
  - On Spring MVC → Enable virtual threads (easy win)
  - Performance critical → Benchmark both approaches
```

---

## Comparison Matrix

### Q9: Complete comparison of all three models

```
┌─────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Aspect          │ Thread-per-Req   │ Event Loop       │ Virtual Threads  │
│                 │ (Tomcat/MVC)     │ (Netty/WebFlux)  │ (Loom/MVC)       │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Threads for     │ 200 (platform)   │ 4-8 (event loop) │ 4-8 (carrier) +  │
│ 10K requests    │                  │                  │ 10K (virtual)    │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Memory usage    │ ~200MB (stacks)  │ ~50MB (heap)     │ ~50MB (heap)     │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Max concurrent  │ ~200-500         │ ~100K+           │ ~1M+             │
│ connections     │                  │                  │                  │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Latency under   │ Degrades (queue) │ Consistent       │ Consistent       │
│ high load       │                  │                  │                  │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ CPU efficiency  │ Low (context     │ High (minimal    │ High (minimal    │
│                 │ switching)       │ switching)       │ switching)       │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Code style      │ Imperative       │ Reactive/        │ Imperative       │
│                 │                  │ Functional       │                  │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Blocking I/O    │ OK (expected)    │ FORBIDDEN        │ OK (yields VT)   │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ ThreadLocal     │ Works            │ Doesn't work     │ Works*           │
│                 │                  │ (use Context)    │ (* use ScopedVal)│
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Error handling  │ try-catch        │ onError*         │ try-catch        │
│                 │                  │ operators        │                  │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Testing         │ Simple           │ StepVerifier     │ Simple           │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Backpressure    │ None             │ Native           │ None             │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Streaming       │ Possible (async) │ Native           │ Possible         │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Maturity        │ 20+ years        │ ~8 years         │ ~2 years         │
└─────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### Q10: Throughput comparison under different loads

```
Scenario: REST API, each request makes 2 DB calls (50ms each) + 1 HTTP call (100ms)
Total I/O time per request: 200ms (if sequential) or 100ms (if parallel)

Metric: Requests/second at different concurrency levels

Concurrent    │ Thread-per-Req │ Event Loop    │ Virtual Threads
Connections   │ (200 threads)  │ (4 EL threads)│ (unlimited VT)
──────────────┼────────────────┼───────────────┼────────────────
100           │  ~900 rps      │  ~950 rps     │  ~950 rps
500           │  ~1800 rps     │  ~4800 rps    │  ~4700 rps
1,000         │  ~1900 rps     │  ~9500 rps    │  ~9300 rps
5,000         │  ~1950 rps     │  ~45000 rps   │  ~43000 rps
10,000        │  ~1950 rps*    │  ~80000 rps   │  ~75000 rps
50,000        │  CONN REFUSED  │  ~200000 rps  │  ~180000 rps

* Thread-per-request plateaus at 200/0.1s = 2000 rps max (threads saturated)
  Requests queue, latency explodes

Note: Actual numbers depend on hardware, network, etc.
These are illustrative of relative performance.
```

---

## When to Use What

### Q11: Decision framework for choosing a threading model

```
START
  │
  ├── Is it Java 21+? 
  │     │
  │     ├── YES: Do you need streaming/backpressure/event-driven?
  │     │         │
  │     │         ├── YES → WebFlux
  │     │         │
  │     │         └── NO → Virtual Threads (simplest high-performance option)
  │     │
  │     └── NO: Are you I/O bound with high concurrency?
  │               │
  │               ├── YES: Can you use reactive libraries for ALL I/O?
  │               │         │
  │               │         ├── YES → WebFlux
  │               │         │
  │               │         └── NO → Spring MVC with async + thread pool tuning
  │               │
  │               └── NO → Spring MVC (traditional)
  │
  └── Special cases:
        ├── Real-time streaming (SSE, WebSocket) → WebFlux
        ├── High-fan-out (API gateway, proxy) → WebFlux or Virtual Threads
        ├── CPU-bound processing → Spring MVC (thread-per-request)
        ├── Team new to reactive → Virtual Threads or Spring MVC
        └── Need complete non-blocking stack → WebFlux
```

### Q12: How do these models handle CPU-intensive work?

```java
// CPU-BOUND WORK (e.g., encryption, image processing, complex calculation)

// Thread-per-request: Fine - thread is doing useful work
@GetMapping("/process")
public Result process(@RequestBody Data data) {
    return heavyComputation(data); // Blocks thread, but CPU is working
}

// Event Loop: DANGEROUS - blocks event loop!
@GetMapping("/process")
public Mono<Result> process(@RequestBody Data data) {
    // WRONG: blocks the event loop thread
    return Mono.just(heavyComputation(data));
    
    // CORRECT: offload to parallel scheduler
    return Mono.fromCallable(() -> heavyComputation(data))
        .subscribeOn(Schedulers.parallel()); // CPU-bound → parallel scheduler
}

// Virtual Threads: Works but wastes carrier thread
@GetMapping("/process")
public Result process(@RequestBody Data data) {
    return heavyComputation(data);
    // VT is pinned to carrier during CPU work (no yield point)
    // Consider using a separate platform thread pool for CPU work
}
```

### Q13: What is Thread Pinning with Virtual Threads?

**Answer:**

Thread pinning occurs when a virtual thread cannot be unmounted from its carrier:

```
Normal (non-pinned):
  VT does I/O → unmount → carrier freed → mount another VT
  
Pinned:
  VT enters synchronized block → CANNOT unmount
  Even if VT does I/O, carrier is STUCK
  
Causes of pinning:
  1. synchronized blocks/methods (use ReentrantLock instead)
  2. JNI/native code execution
  3. CPU-intensive work (no yield point)
```

```java
// PINNING PROBLEM
public class BadService {
    private final Object lock = new Object();
    
    public Data getData() {
        synchronized (lock) {  // PINS the virtual thread!
            return httpClient.send(request); // I/O inside synchronized = disaster
        }
    }
}

// SOLUTION: Use ReentrantLock
public class GoodService {
    private final ReentrantLock lock = new ReentrantLock();
    
    public Data getData() {
        lock.lock();  // Does NOT pin!
        try {
            return httpClient.send(request); // VT can unmount during I/O
        } finally {
            lock.unlock();
        }
    }
}
```

**Detecting pinning:**
```bash
# JVM flag to detect pinning
-Djdk.tracePinnedThreads=short  # Prints stack trace on pinning
-Djdk.tracePinnedThreads=full   # Full stack trace
```

---

## Deep Dive: OS-Level Mechanics

### Q14: How does Java NIO Selector map to OS primitives?

```
┌───────────────────────────────────────────────────────┐
│  Application Layer (Java)                              │
│  java.nio.channels.Selector                           │
│  selector.select() → blocks until events ready        │
└───────────────────┬───────────────────────────────────┘
                    │
┌───────────────────▼───────────────────────────────────┐
│  JVM Native Layer                                      │
│  Maps to OS-specific multiplexing:                     │
│                                                        │
│  Linux:   epoll_wait()    ← O(1) for ready events     │
│  macOS:   kqueue()        ← O(1) for ready events     │
│  Windows: IOCP            ← Completion-based           │
│  Old:     select()/poll() ← O(n) - slow for many FDs  │
└───────────────────────────────────────────────────────┘

epoll (Linux) internals:
  1. epoll_create() → kernel creates epoll instance
  2. epoll_ctl(ADD, fd) → register file descriptors
  3. epoll_wait() → block until ANY registered FD has events
     Kernel maintains a "ready list" - O(1) to check
     Only returns FDs that HAVE events (not all FDs)

Performance:
  select(): O(n) - must scan ALL file descriptors every time
  epoll():  O(k) - only returns k ready descriptors
  
  For 10,000 connections where 10 are active:
    select: checks all 10,000 → returns 10 ready
    epoll:  directly returns 10 ready (kernel maintains ready list)
```

### Q15: Thread context switching cost

```
Context Switch Costs:

Platform Thread (OS thread) switch:
  ├── Save CPU registers (general purpose, FP, SIMD)
  ├── Save stack pointer
  ├── Switch page tables (TLB flush - EXPENSIVE)
  ├── Restore new thread's registers
  ├── Pipeline flush
  └── Cache pollution (L1/L2 likely cold)
  
  Cost: ~1-10 microseconds
  With cache miss: up to 100+ microseconds
  
Virtual Thread switch:
  ├── Save continuation (stack frames → heap)
  ├── No page table switch (same OS thread)
  ├── No TLB flush
  ├── Restore new VT's continuation
  └── Cache mostly warm (same carrier thread)
  
  Cost: ~200-500 nanoseconds (20-50x cheaper!)

Event Loop (no switch at all):
  ├── Just process next event in the loop
  ├── No save/restore (single thread)
  ├── Cache always warm
  └── Zero context switch overhead
  
  Cost: ~0 (just function call overhead)
```

---

## Real-World Architecture Patterns

### Q16: How do companies choose their threading model?

```
Netflix (Heavy Streaming):
  → WebFlux + RxJava
  → Event loop for gateway (Zuul 2)
  → High fan-out, streaming data

LinkedIn (Request-Response + Streaming):
  → Mix: Play Framework (async) + traditional services
  → Moving toward async/non-blocking

Twitter (High Throughput):
  → Finagle (Netty-based, async)
  → Event loop model for extreme throughput

Amazon (Diverse Services):
  → Mix per service needs
  → API Gateway: async (high fan-out)
  → Business logic: thread-per-request
  → Since 2023: Virtual threads for new services

Spring Team Recommendation (2024+):
  → Java 21+ available → Virtual Threads for most use cases
  → Need streaming/backpressure → WebFlux
  → Legacy systems → Thread-per-request with tuning
```

### Q17: Async Servlet (Servlet 3.1) - The Middle Ground

```java
// Async Servlet - releases the container thread
@GetMapping("/async")
public DeferredResult<User> getUser(@PathVariable String id) {
    DeferredResult<User> result = new DeferredResult<>(5000L); // 5s timeout
    
    // Container thread is released HERE
    asyncService.findUser(id, user -> {
        result.setResult(user); // Called from different thread
    });
    
    return result; // Thread returned to pool immediately
}

// Or with CompletableFuture
@GetMapping("/async")
public CompletableFuture<User> getUser(@PathVariable String id) {
    return CompletableFuture.supplyAsync(
        () -> userRepository.findById(id),
        asyncExecutor
    );
}

// Streaming with Servlet 3.1 async
@GetMapping("/stream")
public ResponseBodyEmitter stream() {
    ResponseBodyEmitter emitter = new ResponseBodyEmitter();
    
    asyncExecutor.execute(() -> {
        try {
            for (int i = 0; i < 100; i++) {
                emitter.send("Event " + i + "\n");
                Thread.sleep(100);
            }
            emitter.complete();
        } catch (Exception e) {
            emitter.completeWithError(e);
        }
    });
    
    return emitter; // Container thread released
}
```

```
Async Servlet Timeline:
  Container Thread: [Receive Request][Setup Async][RELEASE] ← ~1ms
  Async Thread:     ────────────────────[DB Call][Build Response][Complete]
  
  Container threads handle MORE requests because they're freed quickly
  But you still need threads for async work (separate pool)
```
