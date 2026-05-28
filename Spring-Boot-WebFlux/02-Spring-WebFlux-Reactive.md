# Spring WebFlux & Reactive Programming - Complete Deep Dive

## Table of Contents
- [Reactive Programming Fundamentals](#reactive-programming-fundamentals)
- [Project Reactor Core Concepts](#project-reactor-core-concepts)
- [Spring WebFlux Architecture](#spring-webflux-architecture)
- [Event Loop Model (Netty)](#event-loop-model-netty)
- [Backpressure](#backpressure)
- [Reactive Operators Deep Dive](#reactive-operators-deep-dive)
- [WebFlux vs WebMVC](#webflux-vs-webmvc)
- [Reactive Data Access](#reactive-data-access)
- [Error Handling in Reactive Streams](#error-handling-in-reactive-streams)
- [Testing Reactive Code](#testing-reactive-code)

---

## Reactive Programming Fundamentals

### Q1: What is Reactive Programming and why does it matter?

**Answer:**

Reactive Programming is a declarative programming paradigm concerned with **data streams** and the **propagation of change**. It's built on the Observer pattern, Iterator pattern, and functional programming.

**The Problem it Solves:**

Traditional blocking I/O:
```
Thread-1: ──────[DB Call]────────────────────[Response]──→ (thread blocked 200ms)
Thread-2: ──────[HTTP Call]──────────────────[Response]──→ (thread blocked 500ms)
Thread-3: ──────[File Read]──────────────────[Response]──→ (thread blocked 100ms)

200 threads = 200 concurrent requests MAX (Tomcat default)
```

Reactive non-blocking I/O:
```
Event Loop: ──[Start DB]──[Start HTTP]──[Start File]──[DB Ready→Process]──[File Ready→Process]──[HTTP Ready→Process]──→

4 threads can handle THOUSANDS of concurrent requests
```

**Reactive Streams Specification (java.util.concurrent.Flow in Java 9+):**

```java
public interface Publisher<T> {
    void subscribe(Subscriber<? super T> subscriber);
}

public interface Subscriber<T> {
    void onSubscribe(Subscription subscription);
    void onNext(T item);
    void onError(Throwable throwable);
    void onComplete();
}

public interface Subscription {
    void request(long n);  // Backpressure mechanism
    void cancel();
}

public interface Processor<T, R> extends Subscriber<T>, Publisher<R> {
    // Both subscriber and publisher - transformation stage
}
```

### Q2: What are the 4 pillars of Reactive Manifesto?

**Answer:**

```
┌─────────────────────────────────────────────────────────┐
│                   REACTIVE SYSTEM                         │
│                                                          │
│  ┌─────────────┐         ┌──────────────┐              │
│  │  RESPONSIVE │ ←────── │  RESILIENT   │              │
│  │  (fast)     │         │  (fault-tolerant)            │
│  └──────┬──────┘         └──────┬───────┘              │
│         │                        │                       │
│         └────────┬───────────────┘                       │
│                  │                                        │
│         ┌────────▼────────┐                              │
│         │    ELASTIC       │                              │
│         │  (scalable)      │                              │
│         └────────┬─────────┘                             │
│                  │                                        │
│         ┌────────▼─────────┐                             │
│         │ MESSAGE DRIVEN   │                             │
│         │ (async, non-blocking, backpressure)            │
│         └──────────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

1. **Responsive** - System responds in a timely manner
2. **Resilient** - System stays responsive in face of failure
3. **Elastic** - System stays responsive under varying workload
4. **Message Driven** - Relies on asynchronous message passing

---

## Project Reactor Core Concepts

### Q3: What is the difference between Mono and Flux?

**Answer:**

```java
// Mono<T> - 0 or 1 element
Mono<User> user = userRepository.findById(id);
// Signals: onSubscribe → [onNext(value)] → onComplete
//     or:  onSubscribe → onError(throwable)

// Flux<T> - 0 to N elements
Flux<User> users = userRepository.findAll();
// Signals: onSubscribe → onNext(v1) → onNext(v2) → ... → onComplete
//     or:  onSubscribe → onNext(v1) → onError(throwable)
```

**Key principle: NOTHING HAPPENS UNTIL YOU SUBSCRIBE**

```java
// This does NOTHING - no HTTP call is made
Mono<Response> response = webClient.get().uri("/api/users").retrieve().bodyToMono(Response.class);

// Only when subscribed does the call happen
response.subscribe(
    value -> log.info("Got: {}", value),     // onNext
    error -> log.error("Error: {}", error),   // onError
    () -> log.info("Completed")               // onComplete
);
```

### Q4: Explain Cold vs Hot Publishers

**Answer:**

```java
// COLD Publisher - data is generated fresh for each subscriber
Flux<Integer> cold = Flux.range(1, 5);
cold.subscribe(i -> System.out.println("Subscriber 1: " + i)); // Gets 1,2,3,4,5
cold.subscribe(i -> System.out.println("Subscriber 2: " + i)); // Gets 1,2,3,4,5 (independent)

// HOT Publisher - data is generated regardless of subscribers
Sinks.Many<String> sink = Sinks.many().multicast().onBackpressureBuffer();
Flux<String> hot = sink.asFlux();

hot.subscribe(s -> System.out.println("Sub1: " + s));
sink.tryEmitNext("Hello");  // Sub1 gets it
hot.subscribe(s -> System.out.println("Sub2: " + s));
sink.tryEmitNext("World");  // Both Sub1 and Sub2 get it
// Sub2 missed "Hello" - that's the nature of hot publishers
```

**Converting Cold to Hot:**
```java
// share() - multicasts to multiple subscribers (hot)
Flux<Long> shared = Flux.interval(Duration.ofSeconds(1)).share();

// cache() - replays all elements to late subscribers
Flux<Long> cached = Flux.interval(Duration.ofSeconds(1)).cache(5); // cache last 5

// replay() + connect() - ConnectableFlux
ConnectableFlux<Long> connectable = Flux.interval(Duration.ofSeconds(1)).publish();
connectable.subscribe(s -> System.out.println("Sub1: " + s));
connectable.connect(); // Start emitting
```

### Q5: What is the Subscription lifecycle in Reactor?

**Answer:**

```
Assembly Time (building the pipeline):
  Mono.just("data")
      .map(String::toUpperCase)
      .flatMap(this::process)
      .subscribe();  ← Triggers Subscription Time

Subscription Time (subscribe propagates upstream):
  subscribe() → calls subscribe on flatMap
    → calls subscribe on map
      → calls subscribe on just
        → just calls onSubscribe(subscription) downstream

Execution Time (data flows downstream):
  just emits "data" via onNext
    → map transforms to "DATA" via onNext
      → flatMap processes asynchronously via onNext
        → subscriber receives result via onNext
          → onComplete signal propagates
```

**Visual:**
```
Assembly:    [Source] ←── [Operator1] ←── [Operator2] ←── [Subscriber]
                                                              │
Subscribe:   ────────────────────────────────────────────────→│
(upstream)                                                     │
                                                              │
Data flow:   │────────────────────────────────────────────────→
(downstream)
```

### Q6: How does the Scheduler work in Reactor?

**Answer:**

```java
// Schedulers control WHICH THREAD executes operations

// publishOn - affects DOWNSTREAM operators (everything after it)
Flux.range(1, 10)
    .map(i -> i * 2)                // Runs on caller thread
    .publishOn(Schedulers.parallel())  // Switch threads HERE
    .map(i -> i + 1)                // Runs on parallel scheduler
    .subscribe();

// subscribeOn - affects the ENTIRE chain (subscription and emission)
Flux.range(1, 10)
    .map(i -> i * 2)                // Runs on boundedElastic
    .subscribeOn(Schedulers.boundedElastic())  // ENTIRE chain on this scheduler
    .map(i -> i + 1)                // Runs on boundedElastic
    .subscribe();
```

**Scheduler Types:**

| Scheduler | Use Case | Threads | Bounded? |
|-----------|----------|---------|----------|
| `Schedulers.immediate()` | Current thread | 0 (reuses) | N/A |
| `Schedulers.single()` | Single reusable thread | 1 | Yes |
| `Schedulers.parallel()` | CPU-bound work | CPU cores | Yes |
| `Schedulers.boundedElastic()` | Blocking I/O wrapping | 10 * CPU cores | Yes (100K tasks) |
| `Schedulers.fromExecutorService()` | Custom thread pool | Custom | Custom |

**Critical Rule:** NEVER block on an event loop thread. Use `subscribeOn(Schedulers.boundedElastic())` to offload blocking calls.

```java
// WRONG - blocks event loop
Mono.fromCallable(() -> blockingJdbcCall())
    .subscribe(); // Runs on event loop thread!

// CORRECT - offload to boundedElastic
Mono.fromCallable(() -> blockingJdbcCall())
    .subscribeOn(Schedulers.boundedElastic())
    .subscribe();
```

---

## Spring WebFlux Architecture

### Q7: Explain the complete WebFlux request processing pipeline

**Answer:**

```
Client HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  NETTY (or Undertow, Tomcat with Servlet 3.1+)          │
│  ├── EventLoopGroup (Boss) - accepts connections        │
│  ├── EventLoopGroup (Worker) - I/O operations           │
│  └── Channel Pipeline (codec, handler)                  │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  HttpHandler (reactive HTTP abstraction)                  │
│  └── Adapts server-specific request/response             │
│      to ServerHttpRequest / ServerHttpResponse           │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  WebHandler API                                          │
│  ├── HttpWebHandlerAdapter                               │
│  ├── ExceptionHandlingWebHandler                         │
│  ├── FilteringWebHandler                                 │
│  │   └── WebFilter chain (reactive filters)             │
│  │       ├── SecurityWebFilter                           │
│  │       ├── CorsWebFilter                               │
│  │       └── Custom WebFilters                           │
│  └── DispatcherHandler                                   │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  DispatcherHandler (reactive front controller)           │
│  ├── 1. HandlerMapping (find handler)                    │
│  │   ├── RequestMappingHandlerMapping (@Controller)     │
│  │   ├── RouterFunctionMapping (functional endpoints)   │
│  │   └── ResourceHandlerMapping (static resources)      │
│  │                                                       │
│  ├── 2. HandlerAdapter (invoke handler)                  │
│  │   ├── RequestMappingHandlerAdapter                    │
│  │   ├── HandlerFunctionAdapter                          │
│  │   └── SimpleHandlerAdapter                            │
│  │                                                       │
│  └── 3. HandlerResultHandler (handle result)             │
│      ├── ResponseEntityResultHandler                     │
│      ├── ServerResponseResultHandler                     │
│      ├── ResponseBodyResultHandler                       │
│      └── ViewResolutionResultHandler                     │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Response written back to client (non-blocking)
```

**Key difference from Spring MVC:**
- Everything returns `Mono<T>` or `Flux<T>`
- No thread-per-request model
- DispatcherHandler returns `Mono<Void>` (completion signal)

### Q8: What is the DispatcherHandler and how does it differ from DispatcherServlet?

**Answer:**

```java
// DispatcherHandler (WebFlux) - REACTIVE
public class DispatcherHandler implements WebHandler {
    
    @Override
    public Mono<Void> handle(ServerWebExchange exchange) {
        return Flux.fromIterable(this.handlerMappings)
            .concatMap(mapping -> mapping.getHandler(exchange))  // Find handler
            .next()
            .switchIfEmpty(createNotFoundError())
            .flatMap(handler -> invokeHandler(exchange, handler))  // Invoke handler
            .flatMap(result -> handleResult(exchange, result));    // Handle result
        // EVERYTHING IS NON-BLOCKING - returns Mono<Void>
    }
}

// DispatcherServlet (MVC) - BLOCKING
public class DispatcherServlet extends HttpServlet {
    
    @Override
    protected void doDispatch(HttpServletRequest request, HttpServletResponse response) {
        HandlerExecutionChain handler = getHandler(request);  // BLOCKING
        HandlerAdapter ha = getHandlerAdapter(handler);       // BLOCKING
        ModelAndView mv = ha.handle(request, response, handler);  // BLOCKING
        processDispatchResult(request, response, handler, mv);    // BLOCKING
    }
}
```

| Aspect | DispatcherServlet | DispatcherHandler |
|--------|------------------|-------------------|
| Base class | HttpServlet | WebHandler |
| Returns | void (writes directly) | Mono<Void> |
| Thread model | Thread-per-request | Event loop |
| Filters | Servlet Filter | WebFilter |
| Request type | HttpServletRequest | ServerWebExchange |
| Blocking? | Yes | No |

### Q9: Explain Annotated Controllers vs Functional Endpoints in WebFlux

**Answer:**

```java
// ANNOTATED CONTROLLERS (familiar Spring MVC style)
@RestController
@RequestMapping("/api/users")
public class UserController {
    
    @GetMapping("/{id}")
    public Mono<User> getUser(@PathVariable String id) {
        return userService.findById(id);
    }
    
    @GetMapping
    public Flux<User> getAllUsers() {
        return userService.findAll();
    }
    
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Mono<User> createUser(@Valid @RequestBody Mono<User> user) {
        return user.flatMap(userService::save);
    }
}

// FUNCTIONAL ENDPOINTS (lambda-based routing)
@Configuration
public class UserRouter {
    
    @Bean
    public RouterFunction<ServerResponse> userRoutes(UserHandler handler) {
        return RouterFunctions
            .route(GET("/api/users/{id}"), handler::getUser)
            .andRoute(GET("/api/users"), handler::getAllUsers)
            .andRoute(POST("/api/users"), handler::createUser)
            .filter((request, next) -> {
                // WebFilter-like behavior
                log.info("Request: {} {}", request.method(), request.path());
                return next.handle(request);
            });
    }
}

@Component
public class UserHandler {
    
    public Mono<ServerResponse> getUser(ServerRequest request) {
        String id = request.pathVariable("id");
        return userService.findById(id)
            .flatMap(user -> ServerResponse.ok().bodyValue(user))
            .switchIfEmpty(ServerResponse.notFound().build());
    }
    
    public Mono<ServerResponse> getAllUsers(ServerRequest request) {
        return ServerResponse.ok()
            .contentType(MediaType.APPLICATION_JSON)
            .body(userService.findAll(), User.class);
    }
    
    public Mono<ServerResponse> createUser(ServerRequest request) {
        return request.bodyToMono(User.class)
            .flatMap(userService::save)
            .flatMap(saved -> ServerResponse.created(URI.create("/api/users/" + saved.getId()))
                .bodyValue(saved));
    }
}
```

**When to use which:**
- Annotated Controllers: Familiar, good IDE support, validation annotations
- Functional Endpoints: More composable, testable without Spring context, better for complex routing

---

## Event Loop Model (Netty)

### Q10: Explain Netty's Event Loop architecture in detail

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│                    NETTY SERVER ARCHITECTURE                       │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Boss EventLoopGroup (1-2 threads)                           │ │
│  │  ┌──────────────┐                                           │ │
│  │  │ EventLoop-1  │  Accepts incoming connections              │ │
│  │  │ (Selector)   │  Registers accepted channels with Worker  │ │
│  │  └──────────────┘                                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│         │ Register channel                                        │
│         ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Worker EventLoopGroup (default: 2 * CPU cores threads)      │ │
│  │                                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │ │
│  │  │ EventLoop-1  │  │ EventLoop-2  │  │ EventLoop-N  │      │ │
│  │  │ (Selector)   │  │ (Selector)   │  │ (Selector)   │      │ │
│  │  │              │  │              │  │              │      │ │
│  │  │ Channel-A ───│  │ Channel-C ───│  │ Channel-E ───│      │ │
│  │  │ Channel-B ───│  │ Channel-D ───│  │ Channel-F ───│      │ │
│  │  │              │  │              │  │              │      │ │
│  │  │ Task Queue   │  │ Task Queue   │  │ Task Queue   │      │ │
│  │  │ ┌─┐┌─┐┌─┐   │  │ ┌─┐┌─┐┌─┐   │  │ ┌─┐┌─┐┌─┐   │      │ │
│  │  │ └─┘└─┘└─┘   │  │ └─┘└─┘└─┘   │  │ └─┘└─┘└─┘   │      │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Each EventLoop:                                                   │
│  ├── Has ONE thread (single-threaded!)                            │
│  ├── Has ONE Selector (Java NIO)                                  │
│  ├── Manages MANY Channels (connections)                          │
│  ├── Processes I/O events + scheduled tasks + queued tasks        │
│  └── NEVER blocks                                                 │
└──────────────────────────────────────────────────────────────────┘
```

**EventLoop execution cycle:**

```java
// Simplified EventLoop run cycle
while (!terminated) {
    // 1. Select ready I/O events (with timeout)
    int readyKeys = selector.select(timeoutMillis);
    
    // 2. Process I/O events
    if (readyKeys > 0) {
        processSelectedKeys();
        // For each ready channel:
        //   - OP_READ → read data from channel → fire channelRead event
        //   - OP_WRITE → write pending data to channel
        //   - OP_ACCEPT → accept new connection
        //   - OP_CONNECT → connection established
    }
    
    // 3. Process task queue (scheduled tasks, submitted tasks)
    runAllTasks(ioRatio);
    // ioRatio controls time split between I/O and tasks (default: 50%)
}
```

### Q11: How does a single thread handle thousands of connections?

**Answer:**

The key insight is **multiplexing** via Java NIO Selector:

```
Traditional (Thread-per-connection):
  Connection-1 → Thread-1 (blocked waiting for data)
  Connection-2 → Thread-2 (blocked waiting for data)
  Connection-3 → Thread-3 (blocked waiting for data)
  ...
  Connection-10000 → Thread-10000 (blocked)
  
  Problem: 10000 threads = massive memory (each thread ~1MB stack)
           + context switching overhead

Event Loop (NIO Multiplexing):
  Selector monitors ALL connections
    │
    ├── Connection-1: no data → skip
    ├── Connection-2: DATA READY → process immediately
    ├── Connection-3: no data → skip
    ├── Connection-4: DATA READY → process immediately
    ...
    └── Connection-10000: no data → skip
    
  ONE thread checks all connections via OS-level epoll/kqueue
  Only processes connections that have data READY
  No blocking, no waiting
```

**Why this works:**
1. Most connections are IDLE most of the time (waiting for client input)
2. Actual CPU work per request is tiny (microseconds)
3. I/O wait dominates (milliseconds to seconds)
4. One thread can handle 100K+ idle connections with minimal memory

### Q12: What happens when you accidentally block an Event Loop thread?

**Answer:**

```java
// CATASTROPHIC - blocks the event loop
@GetMapping("/users/{id}")
public Mono<User> getUser(@PathVariable String id) {
    // This blocks the event loop thread!
    User user = jdbcTemplate.queryForObject("SELECT * FROM users WHERE id = ?", User.class, id);
    return Mono.just(user);
}
```

**Impact:**
```
EventLoop-1 handles 500 connections:
  ├── Connection-1 triggers getUser() → JDBC blocks for 50ms
  │   └── ALL 499 other connections STARVED for 50ms!
  ├── Connection-2, 3, ..., 500 cannot be processed
  └── If 10 requests come in: 10 * 50ms = 500ms starvation

Symptoms:
  - Sudden latency spikes (p99 goes from 5ms to 500ms+)
  - "BlockHound" detects and throws exception
  - Netty logs: "An event executor terminated with non-empty task queue"
```

**Detection with BlockHound:**
```java
// Add to test or application startup
BlockHound.install();

// Will throw:
// reactor.blockhound.BlockingOperationError: 
//   Blocking call! java.io.FileInputStream#readBytes

// How to properly wrap blocking calls:
Mono.fromCallable(() -> jdbcTemplate.queryForObject(...))
    .subscribeOn(Schedulers.boundedElastic());
```

---

## Backpressure

### Q13: What is Backpressure and how does Reactor handle it?

**Answer:**

**Problem:**
```
Fast Producer (100,000 items/sec)  →→→→→→→→→  Slow Consumer (1,000 items/sec)
                                                     ↓
                                              BUFFER OVERFLOW!
                                              OutOfMemoryError!
```

**Solution - Backpressure:**
```
Producer ←─── request(100) ─── Consumer
   │                               │
   │── emit 100 items ──────────→ │ (processes 100 items)
   │                               │
   │←─── request(50) ──────────── │ (ready for more)
   │── emit 50 items ───────────→ │
```

**Reactor's Backpressure Strategies:**

```java
// 1. request(n) - pull-based (default in Reactor)
Flux.range(1, 1000000)
    .subscribe(new BaseSubscriber<Integer>() {
        @Override
        protected void hookOnSubscribe(Subscription subscription) {
            request(10); // Only request 10 items initially
        }
        
        @Override
        protected void hookOnNext(Integer value) {
            process(value);
            request(1); // Request one more after processing
        }
    });

// 2. onBackpressureBuffer() - buffer excess items
Flux.interval(Duration.ofMillis(1))
    .onBackpressureBuffer(1000) // Buffer up to 1000 items
    .subscribe(slowConsumer);

// 3. onBackpressureDrop() - drop items if consumer can't keep up
Flux.interval(Duration.ofMillis(1))
    .onBackpressureDrop(dropped -> log.warn("Dropped: {}", dropped))
    .subscribe(slowConsumer);

// 4. onBackpressureLatest() - keep only the latest item
Flux.interval(Duration.ofMillis(1))
    .onBackpressureLatest()
    .subscribe(slowConsumer);

// 5. onBackpressureError() - error if overflow
Flux.interval(Duration.ofMillis(1))
    .onBackpressureError()
    .subscribe(slowConsumer); // Throws OverflowException
```

### Q14: How does backpressure work across network boundaries (e.g., WebSocket, SSE)?

**Answer:**

```
HTTP/SSE (Server-Sent Events):
  - TCP flow control provides natural backpressure
  - If client can't read fast enough, TCP window fills → server pauses writing
  - Spring WebFlux respects this automatically

WebSocket:
  - No built-in backpressure in WebSocket protocol
  - Must implement application-level backpressure
  - Use Flux with limitRate() or custom request strategies

RSocket (built for reactive):
  - NATIVE backpressure in the protocol
  - request(n) frames sent over the wire
  - Perfect match for Reactor
```

```java
// SSE with natural backpressure
@GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<String>> stream() {
    return Flux.interval(Duration.ofMillis(100))
        .map(i -> ServerSentEvent.builder("Event " + i).build());
    // If client is slow, TCP backpressure kicks in automatically
}

// RSocket with explicit backpressure
@MessageMapping("events")
public Flux<Event> streamEvents() {
    return eventRepository.findAllStreaming()
        .limitRate(100); // Prefetch 100, request more when 75% consumed
}
```

---

## Reactive Operators Deep Dive

### Q15: Explain map vs flatMap vs concatMap vs switchMap

**Answer:**

```java
// map - synchronous 1:1 transformation
Flux.just("hello", "world")
    .map(String::toUpperCase)  // "HELLO", "WORLD"
    // Each input → exactly one output, same thread

// flatMap - async 1:N transformation, INTERLEAVED (no order guarantee)
Flux.just(1, 2, 3)
    .flatMap(id -> webClient.get().uri("/user/" + id).retrieve().bodyToMono(User.class))
    // All 3 requests fire CONCURRENTLY
    // Results arrive in ANY order (whichever completes first)
    // Default concurrency: 256

// concatMap - async 1:N transformation, SEQUENTIAL (preserves order)
Flux.just(1, 2, 3)
    .concatMap(id -> webClient.get().uri("/user/" + id).retrieve().bodyToMono(User.class))
    // Request 1 completes → then request 2 fires → then request 3
    // ORDER PRESERVED but SLOWER

// switchMap - async, CANCELS previous when new item arrives
searchInput.asFlux()
    .switchMap(query -> searchService.search(query))
    // New search term arrives → cancel previous search → start new one
    // Perfect for typeahead/autocomplete
```

**Visual:**
```
flatMap (concurrent, unordered):
  Input:  ──1──────2──────3──────→
  Output: ──────2───1────3───────→  (order not guaranteed)

concatMap (sequential, ordered):
  Input:  ──1──────2──────3──────→
  Output: ──────1──────2──────3──→  (waits for each to complete)

switchMap (cancels previous):
  Input:  ──1──2──────3──────────→
  Output: ────────2(cancelled)──3─→  (only latest matters)
```

### Q16: How does flatMap concurrency work?

```java
// Default concurrency = Queues.SMALL_BUFFER_SIZE = 256
Flux.range(1, 10000)
    .flatMap(i -> processAsync(i))  // Up to 256 concurrent inner publishers

// Control concurrency
Flux.range(1, 10000)
    .flatMap(i -> processAsync(i), 16)  // Max 16 concurrent

// With concurrency AND prefetch
Flux.range(1, 10000)
    .flatMap(i -> processAsync(i), 16, 32)  // concurrency=16, prefetch per inner=32
```

### Q17: Explain zip, merge, concat, combineLatest

```java
// zip - combines elements pairwise (waits for both)
Mono<User> user = userService.findById(id);
Mono<List<Order>> orders = orderService.findByUserId(id);
Mono<UserProfile> profile = Mono.zip(user, orders, (u, o) -> new UserProfile(u, o));
// Both calls run concurrently, combines when BOTH complete

// merge - interleaves multiple publishers (concurrent, unordered)
Flux<Event> events = Flux.merge(
    kafkaEvents,        // All emit concurrently
    websocketEvents,    // Interleaved as they arrive
    databaseEvents
);

// concat - sequential concatenation (ordered)
Flux<Data> allData = Flux.concat(
    cacheSource,     // Try cache first
    databaseSource,  // Then database
    remoteSource     // Then remote
);

// combineLatest - combines latest from each source
Flux<String> combined = Flux.combineLatest(
    priceUpdates,    // When either emits,
    inventoryUpdates, // combine with latest from other
    (price, inventory) -> "Price: " + price + ", Stock: " + inventory
);
```

---

## WebFlux vs WebMVC

### Q18: When should you choose WebFlux over WebMVC?

**Answer:**

| Criteria | Choose WebFlux | Choose WebMVC |
|----------|---------------|---------------|
| I/O pattern | Many concurrent I/O-bound requests | CPU-bound processing |
| Throughput goal | High throughput, low latency | Moderate throughput ok |
| Team experience | Comfortable with reactive | Traditional Java/Spring |
| Data access | Reactive drivers available (R2DBC, reactive Mongo) | JPA/Hibernate (blocking) |
| Dependencies | All can be non-blocking | Has blocking dependencies |
| Debugging | Acceptable with async stack traces | Need simple stack traces |
| Thread model | Event loop acceptable | Thread-per-request preferred |
| Streaming | Need SSE/WebSocket/streaming | Request-response mostly |
| Memory | Memory efficiency critical | Memory less critical |
| Existing code | Greenfield project | Migrating existing MVC app |

**Performance Characteristics:**

```
Load: 10,000 concurrent connections, each making HTTP calls (100ms latency)

Spring MVC (Tomcat, 200 threads):
  - Max concurrent: 200 (limited by thread pool)
  - P99 latency: 500ms+ (queuing when threads exhausted)
  - Memory: ~200MB (thread stacks)
  - Throughput: ~2000 req/sec

Spring WebFlux (Netty, 8 event loop threads):
  - Max concurrent: 10,000+ (event loop handles all)
  - P99 latency: ~105ms (minimal queuing)
  - Memory: ~50MB (no thread-per-request overhead)
  - Throughput: ~10,000+ req/sec

BUT for CPU-intensive work (100ms computation per request):
  - Both handle ~80 req/sec per core (CPU is the bottleneck)
  - WebMVC might be slightly better (less reactive overhead)
```

### Q19: Can you mix WebFlux and WebMVC in the same application?

**Answer:**

**No, you cannot have both in the same Spring Boot application.** Spring Boot detects the `WebApplicationType` at startup and chooses one.

However, you CAN:
```java
// Use reactive WebClient in a WebMVC application
@RestController
public class MvcController {
    
    private final WebClient webClient;
    
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable String id) {
        // WebClient is non-blocking, but we block here to get result
        return webClient.get()
            .uri("/api/users/" + id)
            .retrieve()
            .bodyToMono(User.class)
            .block(); // Blocks the servlet thread - acceptable in MVC
    }
}

// Use Reactor types in MVC controllers (Spring MVC supports this)
@GetMapping("/stream")
public Flux<User> streamUsers() {
    // Spring MVC can handle Flux return types
    // Internally subscribes and writes via async Servlet 3.1
    return userRepository.findAllAsFlux();
}
```

---

## Reactive Data Access

### Q20: How does R2DBC work and how is it different from JDBC?

**Answer:**

```
JDBC (Blocking):
  Thread → getConnection() [blocks] → executeQuery() [blocks] → readResultSet() [blocks] → close()
  Thread is blocked during ALL database operations

R2DBC (Non-Blocking):
  EventLoop → getConnection() [returns Mono] → executeQuery() [returns Flux] → stream results → release
  Event loop is NEVER blocked
```

```java
// R2DBC reactive repository
public interface UserRepository extends ReactiveCrudRepository<User, Long> {
    Flux<User> findByLastName(String lastName);
    
    @Query("SELECT * FROM users WHERE email = :email")
    Mono<User> findByEmail(String email);
}

// Using DatabaseClient for complex queries
@Repository
public class CustomUserRepository {
    private final DatabaseClient client;
    
    public Flux<User> findActiveUsers() {
        return client.sql("SELECT * FROM users WHERE active = true")
            .map(row -> new User(
                row.get("id", Long.class),
                row.get("name", String.class),
                row.get("email", String.class)
            ))
            .all();
    }
    
    // Transactional support
    @Transactional
    public Mono<User> createUser(User user) {
        return client.sql("INSERT INTO users (name, email) VALUES (:name, :email)")
            .bind("name", user.getName())
            .bind("email", user.getEmail())
            .fetch()
            .rowsUpdated()
            .thenReturn(user);
    }
}
```

**R2DBC Connection Pool:**
```java
@Configuration
public class R2dbcConfig {
    @Bean
    public ConnectionFactory connectionFactory() {
        return ConnectionFactories.get(ConnectionFactoryOptions.builder()
            .option(DRIVER, "pool")     // Use pooling
            .option(PROTOCOL, "postgresql")
            .option(HOST, "localhost")
            .option(PORT, 5432)
            .option(DATABASE, "mydb")
            .option(USER, "postgres")
            .option(PASSWORD, "secret")
            .option(MAX_SIZE, 20)       // Max pool size
            .option(INITIAL_SIZE, 5)    // Initial pool size
            .build());
    }
}
```

---

## Error Handling in Reactive Streams

### Q21: How do you handle errors in reactive chains?

**Answer:**

```java
// 1. onErrorReturn - static fallback value
userService.findById(id)
    .onErrorReturn(new User("default", "Unknown"));

// 2. onErrorResume - dynamic fallback (another publisher)
userService.findById(id)
    .onErrorResume(NotFoundException.class, e -> Mono.empty())
    .onErrorResume(ServiceException.class, e -> cacheService.getCachedUser(id));

// 3. onErrorMap - transform error type
userService.findById(id)
    .onErrorMap(R2dbcException.class, e -> new ServiceException("DB Error", e));

// 4. doOnError - side effect (logging), doesn't handle error
userService.findById(id)
    .doOnError(e -> log.error("Failed to find user: {}", id, e))
    .onErrorResume(e -> Mono.empty());

// 5. retry - retry on error
webClient.get().uri("/api/data")
    .retrieve()
    .bodyToMono(Data.class)
    .retryWhen(Retry.backoff(3, Duration.ofMillis(100))
        .maxBackoff(Duration.ofSeconds(2))
        .filter(e -> e instanceof WebClientResponseException.ServiceUnavailable));

// 6. timeout - error if too slow
webClient.get().uri("/api/data")
    .retrieve()
    .bodyToMono(Data.class)
    .timeout(Duration.ofSeconds(5))
    .onErrorResume(TimeoutException.class, e -> Mono.just(fallbackData));
```

**Global Error Handling in WebFlux:**

```java
@ControllerAdvice
public class GlobalErrorHandler {
    
    @ExceptionHandler(NotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Mono<ErrorResponse> handleNotFound(NotFoundException e) {
        return Mono.just(new ErrorResponse(404, e.getMessage()));
    }
    
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public Mono<ErrorResponse> handleGeneral(Exception e) {
        log.error("Unhandled error", e);
        return Mono.just(new ErrorResponse(500, "Internal Server Error"));
    }
}

// Or using WebExceptionHandler for lower-level control
@Component
@Order(-2) // Before default handler
public class CustomWebExceptionHandler implements WebExceptionHandler {
    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable ex) {
        if (ex instanceof CustomException) {
            exchange.getResponse().setStatusCode(HttpStatus.BAD_REQUEST);
            byte[] bytes = "Bad Request".getBytes(StandardCharsets.UTF_8);
            DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(bytes);
            return exchange.getResponse().writeWith(Mono.just(buffer));
        }
        return Mono.error(ex); // Propagate to next handler
    }
}
```

---

## Testing Reactive Code

### Q22: How do you test reactive code with StepVerifier?

**Answer:**

```java
// StepVerifier - the primary testing tool for Reactor

// Test Mono
@Test
void testFindUser() {
    Mono<User> result = userService.findById("123");
    
    StepVerifier.create(result)
        .assertNext(user -> {
            assertThat(user.getId()).isEqualTo("123");
            assertThat(user.getName()).isEqualTo("John");
        })
        .verifyComplete(); // Asserts onComplete signal
}

// Test Flux
@Test
void testFindAllUsers() {
    Flux<User> result = userService.findAll();
    
    StepVerifier.create(result)
        .expectNextCount(3)
        .verifyComplete();
}

// Test errors
@Test
void testUserNotFound() {
    Mono<User> result = userService.findById("nonexistent");
    
    StepVerifier.create(result)
        .verifyError(NotFoundException.class);
}

// Test with virtual time (for time-based operators)
@Test
void testInterval() {
    StepVerifier.withVirtualTime(() -> Flux.interval(Duration.ofHours(1)).take(3))
        .expectSubscription()
        .expectNoEvent(Duration.ofHours(1))
        .expectNext(0L)
        .thenAwait(Duration.ofHours(2))
        .expectNext(1L, 2L)
        .verifyComplete();
}

// WebTestClient for integration tests
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class UserControllerTest {
    
    @Autowired
    private WebTestClient webTestClient;
    
    @Test
    void testGetUser() {
        webTestClient.get().uri("/api/users/123")
            .exchange()
            .expectStatus().isOk()
            .expectBody(User.class)
            .value(user -> assertThat(user.getName()).isEqualTo("John"));
    }
    
    @Test
    void testStreamUsers() {
        webTestClient.get().uri("/api/users/stream")
            .accept(MediaType.TEXT_EVENT_STREAM)
            .exchange()
            .expectStatus().isOk()
            .returnResult(User.class)
            .getResponseBody()
            .as(StepVerifier::create)
            .expectNextCount(10)
            .thenCancel()
            .verify();
    }
}
```

---

## WebClient (Reactive HTTP Client)

### Q23: How does WebClient work and when should you use it?

**Answer:**

```java
// WebClient - non-blocking, reactive HTTP client (replaces RestTemplate)

// Configuration
@Bean
public WebClient webClient() {
    return WebClient.builder()
        .baseUrl("https://api.example.com")
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .filter(ExchangeFilterFunction.ofRequestProcessor(request -> {
            log.info("Request: {} {}", request.method(), request.url());
            return Mono.just(request);
        }))
        .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
        .build();
}

// Usage
public Mono<User> getUser(String id) {
    return webClient.get()
        .uri("/users/{id}", id)
        .header("Authorization", "Bearer " + token)
        .retrieve()
        .onStatus(HttpStatusCode::is4xxClientError, response ->
            response.bodyToMono(String.class)
                .flatMap(body -> Mono.error(new ClientException(body))))
        .onStatus(HttpStatusCode::is5xxServerError, response ->
            Mono.error(new ServerException("Server error")))
        .bodyToMono(User.class)
        .timeout(Duration.ofSeconds(5))
        .retryWhen(Retry.backoff(3, Duration.ofMillis(500)));
}

// Parallel calls with WebClient
public Mono<UserDashboard> getDashboard(String userId) {
    Mono<User> user = getUser(userId);
    Mono<List<Order>> orders = getOrders(userId);
    Mono<Preferences> prefs = getPreferences(userId);
    
    // All three calls execute CONCURRENTLY
    return Mono.zip(user, orders, prefs)
        .map(tuple -> new UserDashboard(tuple.getT1(), tuple.getT2(), tuple.getT3()));
}
```

### Q24: WebClient connection pool and timeout configuration

```java
@Bean
public WebClient webClient() {
    // Configure connection pool
    ConnectionProvider provider = ConnectionProvider.builder("custom")
        .maxConnections(500)                    // Max total connections
        .maxIdleTime(Duration.ofSeconds(20))    // Close idle connections after 20s
        .maxLifeTime(Duration.ofMinutes(5))     // Close connections after 5min
        .pendingAcquireTimeout(Duration.ofSeconds(60)) // Wait for connection
        .evictInBackground(Duration.ofSeconds(30))     // Background eviction
        .build();
    
    // Configure timeouts
    HttpClient httpClient = HttpClient.create(provider)
        .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)  // TCP connect timeout
        .responseTimeout(Duration.ofSeconds(10))              // Response timeout
        .doOnConnected(conn -> conn
            .addHandlerLast(new ReadTimeoutHandler(10, TimeUnit.SECONDS))
            .addHandlerLast(new WriteTimeoutHandler(10, TimeUnit.SECONDS)));
    
    return WebClient.builder()
        .clientConnector(new ReactorClientHttpConnector(httpClient))
        .build();
}
```

---

## Context Propagation

### Q25: How does Reactor Context work (replacing ThreadLocal)?

**Answer:**

**Problem:** ThreadLocal doesn't work in reactive because operators may execute on different threads.

```java
// ThreadLocal approach (BROKEN in reactive)
public class SecurityContext {
    private static final ThreadLocal<User> currentUser = new ThreadLocal<>();
    // Won't work because reactive operators switch threads!
}

// Reactor Context approach (CORRECT)
public Mono<Order> createOrder(Order order) {
    return Mono.deferContextual(ctx -> {
        String userId = ctx.get("userId");  // Read from context
        String traceId = ctx.get("traceId");
        order.setCreatedBy(userId);
        return orderRepository.save(order);
    });
}

// Setting context (at subscription point, flows UPSTREAM)
orderService.createOrder(order)
    .contextWrite(Context.of("userId", "user123", "traceId", UUID.randomUUID().toString()))
    .subscribe();

// WebFilter to set context for all requests
@Component
public class ContextWebFilter implements WebFilter {
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String traceId = exchange.getRequest().getHeaders().getFirst("X-Trace-Id");
        return chain.filter(exchange)
            .contextWrite(Context.of("traceId", traceId != null ? traceId : UUID.randomUUID().toString()));
    }
}
```

**Context propagation direction:**
```
Context flows UPSTREAM (from subscriber to publisher):

Publisher ──op1──op2──op3──Subscriber
                              │
Context: ←←←←←←←←←←←←←←←←←┘

// contextWrite() is placed AFTER the operators that need the context
// but the context is available to ALL operators ABOVE it
```

---

## Server-Sent Events & WebSocket

### Q26: How to implement real-time streaming with WebFlux?

**Answer:**

```java
// Server-Sent Events (SSE)
@GetMapping(value = "/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<Event>> streamEvents() {
    return eventService.getEventStream()
        .map(event -> ServerSentEvent.<Event>builder()
            .id(event.getId())
            .event(event.getType())
            .data(event)
            .retry(Duration.ofSeconds(5))
            .build());
}

// WebSocket with WebFlux
@Configuration
public class WebSocketConfig {
    @Bean
    public HandlerMapping webSocketMapping() {
        Map<String, WebSocketHandler> map = new HashMap<>();
        map.put("/ws/chat", new ChatWebSocketHandler());
        
        SimpleUrlHandlerMapping mapping = new SimpleUrlHandlerMapping();
        mapping.setUrlMap(map);
        mapping.setOrder(-1);
        return mapping;
    }
}

public class ChatWebSocketHandler implements WebSocketHandler {
    private final Sinks.Many<String> sink = Sinks.many().multicast().onBackpressureBuffer();
    
    @Override
    public Mono<Void> handle(WebSocketSession session) {
        // Receive messages from client
        Mono<Void> input = session.receive()
            .map(WebSocketMessage::getPayloadAsText)
            .doOnNext(msg -> sink.tryEmitNext(msg))
            .then();
        
        // Send messages to client
        Mono<Void> output = session.send(
            sink.asFlux()
                .map(session::textMessage)
        );
        
        // Both run concurrently
        return Mono.zip(input, output).then();
    }
}
```
