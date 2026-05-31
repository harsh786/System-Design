# WebFlux & Reactive Interview Questions (50 Questions)

## Table of Contents
- [Reactor Core (Q1-Q15)](#reactor-core)
- [WebFlux Architecture (Q16-Q25)](#webflux-architecture)
- [Reactive Data Access (Q26-Q35)](#reactive-data-access)
- [Production Patterns (Q36-Q45)](#production-patterns)
- [Performance (Q46-Q50)](#performance)

---

## Reactor Core

### Q1: Explain the complete signal lifecycle of Mono and Flux

```
Mono<T> signals:
  onSubscribe(Subscription) → [onNext(T)] → onComplete()
  onSubscribe(Subscription) → onError(Throwable)
  onSubscribe(Subscription) → onComplete()  (empty Mono)

Flux<T> signals:
  onSubscribe(Subscription) → onNext(T1) → onNext(T2) → ... → onComplete()
  onSubscribe(Subscription) → onNext(T1) → onError(Throwable)
  onSubscribe(Subscription) → onComplete()  (empty Flux)

Key rules:
  - onSubscribe ALWAYS called first (exactly once)
  - onNext can be called 0 to N times
  - Terminal signal: EITHER onComplete() OR onError() (exactly once, mutually exclusive)
  - After terminal signal, NO more signals
  - Subscription.request(n) controls how many onNext signals subscriber wants
```

```java
// Observing all signals:
Flux.just("A", "B", "C")
    .doOnSubscribe(sub -> log.info("Subscribed: {}", sub))
    .doOnRequest(n -> log.info("Requested: {}", n))
    .doOnNext(item -> log.info("Next: {}", item))
    .doOnComplete(() -> log.info("Complete"))
    .doOnError(e -> log.error("Error: {}", e.getMessage()))
    .doFinally(signal -> log.info("Finally: {}", signal))
    .subscribe();

// Output:
// Subscribed: FluxArray.ArraySubscription
// Requested: 9223372036854775807 (Long.MAX_VALUE = unbounded)
// Next: A
// Next: B
// Next: C
// Complete
// Finally: onComplete
```

---

### Q2: Explain Assembly time vs Subscription time vs Execution time

```
ASSEMBLY TIME (building the pipeline):
  - When you write the chain of operators
  - NO data flows yet
  - Just creates a description of the computation
  - Like writing SQL without executing it

  Mono<User> pipeline = userRepo.findById(id)  // Assembly
      .map(User::getName)                       // Assembly
      .flatMap(name -> process(name));          // Assembly
  // NOTHING has happened yet!

SUBSCRIPTION TIME (subscribe propagates upstream):
  - Triggered by .subscribe(), .block(), or framework subscription
  - Subscribe signal propagates from subscriber UP to source
  - Operators set up internal state
  - Subscription object passed downstream

  pipeline.subscribe(result -> log.info("Got: {}", result));
  // Now subscription propagates:
  // Subscriber → flatMap → map → findById → Database driver

EXECUTION TIME (data flows downstream):
  - After subscription, source starts emitting
  - Data flows from source DOWN through operators
  - Each operator transforms and passes to next

  Database emits User → map extracts name → flatMap processes → subscriber receives
```

```
Visual:

Assembly:    Source ← op1 ← op2 ← op3    (operators created, linked)
                                    
Subscribe:   Source ← op1 ← op2 ← op3 ← Subscriber  (subscribe propagates UP)
                                    
Execution:   Source → op1 → op2 → op3 → Subscriber  (data flows DOWN)
```

---

### Q3: map vs flatMap vs concatMap vs switchMap - with visual diagrams

```java
// MAP: Synchronous 1:1 transformation (never changes cardinality)
Flux.just(1, 2, 3)
    .map(i -> i * 10)    // 10, 20, 30
    // Input:  ──1────2────3──|
    // Output: ──10───20───30─|

// FLATMAP: Async 1:N, CONCURRENT, NO ORDER GUARANTEE
Flux.just(1, 2, 3)
    .flatMap(i -> fetchFromApi(i))  // Results in ANY order
    // Input:  ──1──────2──────3──────|
    // Inner:    └→[A1,A2]  (completes at t=3)
    //              └→[B1,B2]  (completes at t=1)
    //                 └→[C1,C2]  (completes at t=2)
    // Output: ──B1─B2─C1─C2─A1─A2──|  (interleaved, unordered!)
    
    // Default concurrency: 256 inner subscriptions

// CONCATMAP: Async 1:N, SEQUENTIAL, ORDER PRESERVED
Flux.just(1, 2, 3)
    .concatMap(i -> fetchFromApi(i))  // Wait for each to complete
    // Input:  ──1──────2──────3──────|
    // Inner:    └→[A1,A2]| then [B1,B2]| then [C1,C2]|
    // Output: ──A1─A2─B1─B2─C1─C2──|  (ordered, sequential)
    
    // Only subscribes to next inner when previous completes

// SWITCHMAP: Async, CANCELS previous on new item
Flux.just(1, 2, 3)
    .switchMap(i -> fetchFromApi(i))  // Cancel previous on new
    // Input:  ──1──2──────3──────|
    // Inner:    └→[A1,A2] ← CANCELLED when 2 arrives
    //              └→[B1,B2] ← CANCELLED when 3 arrives
    //                 └→[C1,C2]  (only this completes)
    // Output: ──C1─C2──|  (only latest matters)
    
    // Perfect for: autocomplete, search-as-you-type
```

---

### Q4: Explain backpressure mechanisms in detail

```java
// PROBLEM: Fast publisher, slow subscriber
Flux.interval(Duration.ofMillis(1))  // 1000 items/sec
    .subscribe(item -> {
        Thread.sleep(100);  // Can only process 10/sec
        process(item);
    });
// Without backpressure: OutOfMemoryError (items buffer indefinitely)

// SOLUTION 1: request(n) - Subscriber controls pace
Flux.range(1, 1000000)
    .subscribe(new BaseSubscriber<>() {
        @Override
        protected void hookOnSubscribe(Subscription s) {
            request(10);  // "I can handle 10 items"
        }
        @Override
        protected void hookOnNext(Integer value) {
            process(value);
            request(1);   // "Give me 1 more"
        }
    });

// SOLUTION 2: onBackpressureBuffer
Flux.interval(Duration.ofMillis(1))
    .onBackpressureBuffer(
        1000,                          // Buffer size
        item -> log.warn("Overflow!"), // Overflow callback
        BufferOverflowStrategy.DROP_OLDEST  // Strategy when full
    )
    .subscribe(slowConsumer);

// SOLUTION 3: onBackpressureDrop
Flux.interval(Duration.ofMillis(1))
    .onBackpressureDrop(dropped -> metrics.increment("dropped"))
    .subscribe(slowConsumer);
// Drops items subscriber can't handle

// SOLUTION 4: onBackpressureLatest
Flux.interval(Duration.ofMillis(1))
    .onBackpressureLatest()
    .subscribe(slowConsumer);
// Keeps only the LATEST item, drops intermediate

// SOLUTION 5: limitRate (prefetch control)
Flux.range(1, 1000000)
    .limitRate(100)  // Request 100, replenish at 75% (75 consumed → request 75 more)
    .subscribe(consumer);
// Controls upstream request size - prevents fetching too much at once
```

---

### Q5: Hot vs Cold publishers with real examples

```java
// COLD: Each subscriber gets ALL data from beginning (like a DVD)
// Data is generated PER SUBSCRIBER
Flux<String> cold = Flux.defer(() -> {
    log.info("Generating data");
    return Flux.just("A", "B", "C");
});
cold.subscribe(s -> log.info("Sub1: " + s)); // Gets A, B, C
cold.subscribe(s -> log.info("Sub2: " + s)); // Gets A, B, C (independent!)
// "Generating data" printed TWICE

// Real cold example: HTTP request
Mono<Response> apiCall = webClient.get().uri("/data").retrieve().bodyToMono(Response.class);
apiCall.subscribe(...); // Makes HTTP call
apiCall.subscribe(...); // Makes ANOTHER HTTP call (independent!)

// HOT: Data exists regardless of subscribers (like live TV)
// share() - converts cold to hot
Flux<Long> hot = Flux.interval(Duration.ofSeconds(1))
    .share();  // Multicasts to all subscribers
    
hot.subscribe(s -> log.info("Sub1: " + s)); // t=0: gets 0, 1, 2, ...
Thread.sleep(3000);
hot.subscribe(s -> log.info("Sub2: " + s)); // t=3: gets 3, 4, 5, ... (missed 0,1,2!)

// Sinks - native hot publisher
Sinks.Many<String> sink = Sinks.many().multicast().onBackpressureBuffer();
Flux<String> hotFlux = sink.asFlux();

hotFlux.subscribe(s -> log.info("Sub1: " + s));
sink.tryEmitNext("Hello");  // Sub1 gets it
hotFlux.subscribe(s -> log.info("Sub2: " + s));
sink.tryEmitNext("World");  // Both get it
// Sub2 missed "Hello"

// replay() - hot with history
Flux<String> replayed = sink.asFlux().replay(5).autoConnect();
// New subscribers get last 5 items + live items

// cache() - cold that caches result
Mono<Config> cachedConfig = loadConfig().cache(Duration.ofMinutes(5));
// First subscriber triggers load, subsequent get cached result for 5min
```

---

### Q6: Reactor Context - replacing ThreadLocal

```java
// PROBLEM: ThreadLocal doesn't work in reactive (thread switching)
// MDC.put("traceId", id) → lost when operator switches threads

// SOLUTION: Reactor Context (immutable, flows UPSTREAM)
public Mono<Order> createOrder(Order order) {
    return Mono.deferContextual(ctx -> {
        // Read from context
        String userId = ctx.get("userId");
        String traceId = ctx.get("traceId");
        order.setCreatedBy(userId);
        log.info("[{}] Creating order for user {}", traceId, userId);
        return orderRepo.save(order);
    });
}

// Writing context (at subscription point)
orderService.createOrder(order)
    .contextWrite(Context.of("userId", "user-123"))
    .contextWrite(Context.of("traceId", UUID.randomUUID().toString()))
    .subscribe();

// Context in WebFilter (applies to all requests)
@Component
public class TraceContextFilter implements WebFilter {
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String traceId = exchange.getRequest().getHeaders()
            .getFirst("X-Trace-Id");
        if (traceId == null) traceId = UUID.randomUUID().toString();

        String finalTraceId = traceId;
        return chain.filter(exchange)
            .contextWrite(ctx -> ctx.put("traceId", finalTraceId));
    }
}

// KEY INSIGHT: Context flows UPSTREAM
// contextWrite placed AFTER operators, but available to operators ABOVE it
Mono.just("data")
    .flatMap(d -> {
        // Can access context here
        return Mono.deferContextual(ctx -> Mono.just(ctx.get("key")));
    })
    .contextWrite(Context.of("key", "value")); // Placed after, but available above!
```

---

### Q7: publishOn vs subscribeOn - which thread runs what?

```java
// subscribeOn: Affects the ENTIRE chain (subscription + emission)
// Only the FIRST subscribeOn matters (closest to source)
Flux.range(1, 5)                           // Runs on: boundedElastic
    .map(i -> {
        log.info("map1 on: " + Thread.currentThread().getName());
        return i * 2;                       // Runs on: boundedElastic
    })
    .subscribeOn(Schedulers.boundedElastic()) // Affects EVERYTHING above
    .map(i -> {
        log.info("map2 on: " + Thread.currentThread().getName());
        return i + 1;                       // Runs on: boundedElastic
    })
    .subscribe();
// ENTIRE chain runs on boundedElastic

// publishOn: Affects DOWNSTREAM operators (everything after it)
Flux.range(1, 5)                           // Runs on: caller thread
    .map(i -> {
        log.info("map1 on: " + Thread.currentThread().getName());
        return i * 2;                       // Runs on: caller thread
    })
    .publishOn(Schedulers.parallel())       // Switch HERE
    .map(i -> {
        log.info("map2 on: " + Thread.currentThread().getName());
        return i + 1;                       // Runs on: parallel
    })
    .subscribe();
// map1 on caller thread, map2 on parallel scheduler

// COMBINING both:
Flux.create(sink -> {
        log.info("emit on: " + Thread.currentThread().getName());
        sink.next(1);
        sink.complete();
    })
    .subscribeOn(Schedulers.boundedElastic())  // Source emits on: boundedElastic
    .publishOn(Schedulers.parallel())          // Downstream runs on: parallel
    .map(i -> {
        log.info("map on: " + Thread.currentThread().getName());
        return i;                              // Runs on: parallel
    })
    .subscribe();
```

---

### Q8: Error handling operators hierarchy

```java
// 1. onErrorReturn - static fallback value
userService.findById(id)
    .onErrorReturn(new User("default"));  // On ANY error, return this
    
userService.findById(id)
    .onErrorReturn(NotFoundException.class, new User("not-found")); // Specific error type

// 2. onErrorResume - dynamic fallback (another publisher)
userService.findById(id)
    .onErrorResume(NotFoundException.class, e -> Mono.empty())
    .onErrorResume(TimeoutException.class, e -> cacheService.getCached(id))
    .onErrorResume(e -> Mono.error(new ServiceException("Wrapped", e)));

// 3. onErrorMap - transform error type (don't handle, just transform)
userService.findById(id)
    .onErrorMap(R2dbcException.class, e -> new DataAccessException("DB error", e));

// 4. onErrorComplete - swallow error, complete normally
userService.findById(id)
    .onErrorComplete(NotFoundException.class); // Error → empty completion

// 5. retry - simple retry N times
webClient.get().uri("/api")
    .retrieve().bodyToMono(Data.class)
    .retry(3); // Retry up to 3 times on ANY error

// 6. retryWhen - advanced retry with backoff
webClient.get().uri("/api")
    .retrieve().bodyToMono(Data.class)
    .retryWhen(Retry.backoff(3, Duration.ofMillis(100))
        .maxBackoff(Duration.ofSeconds(5))
        .jitter(0.5)
        .filter(e -> e instanceof WebClientResponseException.ServiceUnavailable)
        .doBeforeRetry(signal -> log.warn("Retrying: attempt {}", signal.totalRetries()))
        .onRetryExhaustedThrow((spec, signal) -> signal.failure()));

// 7. timeout + fallback combination
webClient.get().uri("/api")
    .retrieve().bodyToMono(Data.class)
    .timeout(Duration.ofSeconds(3))
    .onErrorResume(TimeoutException.class, e -> getCachedData())
    .retryWhen(Retry.fixedDelay(2, Duration.ofMillis(500))
        .filter(e -> !(e instanceof TimeoutException)));

// 8. doOnError - side effect only (logging), doesn't handle
userService.findById(id)
    .doOnError(e -> log.error("Error finding user {}: {}", id, e.getMessage()))
    .onErrorResume(e -> Mono.empty()); // Still need to handle!
```

---

### Q9: Testing with StepVerifier

```java
// Basic assertion
@Test
void testFlux() {
    Flux<String> source = Flux.just("A", "B", "C");
    
    StepVerifier.create(source)
        .expectNext("A")
        .expectNext("B")
        .expectNext("C")
        .verifyComplete();  // Asserts onComplete signal
}

// Error assertion
@Test
void testError() {
    Mono<User> source = userService.findById("nonexistent");
    
    StepVerifier.create(source)
        .verifyError(NotFoundException.class);
}

// With assertion on elements
@Test
void testWithAssertions() {
    Flux<User> users = userService.findByAge(18, 30);
    
    StepVerifier.create(users)
        .assertNext(user -> {
            assertThat(user.getAge()).isBetween(18, 30);
            assertThat(user.getName()).isNotBlank();
        })
        .expectNextCount(9)  // 9 more elements
        .verifyComplete();
}

// Virtual time (for time-based operators)
@Test
void testInterval() {
    StepVerifier.withVirtualTime(() -> 
            Flux.interval(Duration.ofHours(1)).take(3))
        .expectSubscription()
        .expectNoEvent(Duration.ofHours(1))  // Nothing for 1 hour
        .expectNext(0L)
        .thenAwait(Duration.ofHours(2))      // Fast-forward 2 hours
        .expectNext(1L, 2L)
        .verifyComplete();
}

// Testing backpressure
@Test
void testBackpressure() {
    Flux<Integer> source = Flux.range(1, 100);
    
    StepVerifier.create(source, 5)  // Initial request = 5
        .expectNextCount(5)
        .thenRequest(3)              // Request 3 more
        .expectNextCount(3)
        .thenCancel()               // Cancel subscription
        .verify();
}

// Testing context
@Test
void testContext() {
    Mono<String> source = Mono.deferContextual(ctx -> Mono.just(ctx.get("key")));
    
    StepVerifier.create(source.contextWrite(Context.of("key", "value")))
        .expectNext("value")
        .verifyComplete();
}
```

---

## WebFlux Architecture

### Q16: How does Netty integrate with WebFlux?

```
Request Flow: Netty → Reactor Netty → Spring WebFlux

Netty Channel Pipeline:
  ┌─────────────────────────────────────────────────────────┐
  │ Channel Pipeline                                         │
  │ ┌──────────────┐  ┌────────────┐  ┌─────────────────┐  │
  │ │ HttpDecoder  │→ │HttpAggregat│→ │ReactorNettyHandler│ │
  │ │(bytes→HTTP)  │  │(chunks→full)│  │(HTTP→WebFlux)    │ │
  │ └──────────────┘  └────────────┘  └─────────────────┘  │
  └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ ReactorHttpHandlerAdapter                                │
  │ Converts: HttpServerRequest → ServerHttpRequest          │
  │           HttpServerResponse → ServerHttpResponse        │
  └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ HttpWebHandlerAdapter → WebHandler API                   │
  │ → FilteringWebHandler (WebFilter chain)                  │
  │ → DispatcherHandler                                      │
  │   → HandlerMapping → HandlerAdapter → ResultHandler      │
  └─────────────────────────────────────────────────────────┘
```

```java
// Netty configuration in Spring WebFlux
@Bean
public NettyReactiveWebServerFactory nettyFactory() {
    NettyReactiveWebServerFactory factory = new NettyReactiveWebServerFactory();
    factory.addServerCustomizers(httpServer -> httpServer
        .option(ChannelOption.SO_BACKLOG, 128)
        .childOption(ChannelOption.SO_KEEPALIVE, true)
        .childOption(ChannelOption.TCP_NODELAY, true)
        .accessLog(true)
        .wiretap(true)  // Enable wire logging for debugging
    );
    return factory;
}

// Event loop thread configuration
@Bean
public ReactorResourceFactory reactorResourceFactory() {
    ReactorResourceFactory factory = new ReactorResourceFactory();
    factory.setLoopResources(LoopResources.create(
        "http",
        1,   // select (acceptor) threads
        Runtime.getRuntime().availableProcessors(), // worker threads
        true  // daemon
    ));
    return factory;
}
```

---

### Q17: WebFilter vs HandlerFilterFunction

```java
// WebFilter: Applies to ALL requests (like Servlet Filter)
@Component
@Order(1)
public class AuthWebFilter implements WebFilter {
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String token = exchange.getRequest().getHeaders().getFirst("Authorization");
        if (token == null) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }
        return chain.filter(exchange)
            .contextWrite(ctx -> ctx.put("userId", extractUser(token)));
    }
}

// HandlerFilterFunction: Applies to specific RouterFunction routes
@Bean
public RouterFunction<ServerResponse> routes(UserHandler handler) {
    return RouterFunctions
        .route(GET("/api/users"), handler::listUsers)
        .filter((request, next) -> {
            // Only applies to these routes
            log.info("Request: {} {}", request.method(), request.path());
            long start = System.currentTimeMillis();
            return next.handle(request)
                .doOnSuccess(response -> 
                    log.info("Response: {} in {}ms", 
                        response.statusCode(), 
                        System.currentTimeMillis() - start));
        });
}
```

| Aspect | WebFilter | HandlerFilterFunction |
|--------|-----------|----------------------|
| Scope | All requests | Specific routes |
| Registration | @Component / @Bean | .filter() on RouterFunction |
| Access to | ServerWebExchange | ServerRequest/ServerResponse |
| Use case | Cross-cutting (auth, logging) | Route-specific logic |

---

### Q18: WebClient internals and connection pooling

```java
// WebClient uses Reactor Netty's HttpClient internally
// Connection pool is managed by ConnectionProvider

@Bean
public WebClient webClient() {
    // Connection pool configuration
    ConnectionProvider provider = ConnectionProvider.builder("custom")
        .maxConnections(500)                     // Total max connections
        .maxIdleTime(Duration.ofSeconds(20))     // Close idle after 20s
        .maxLifeTime(Duration.ofMinutes(5))      // Force close after 5min
        .pendingAcquireTimeout(Duration.ofSeconds(60)) // Wait for connection
        .pendingAcquireMaxCount(1000)            // Max pending requests
        .evictInBackground(Duration.ofSeconds(30)) // Background eviction
        .metrics(true)                           // Enable metrics
        .build();

    // HTTP client with timeouts
    HttpClient httpClient = HttpClient.create(provider)
        .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
        .responseTimeout(Duration.ofSeconds(10))
        .doOnConnected(conn -> conn
            .addHandlerLast(new ReadTimeoutHandler(10))
            .addHandlerLast(new WriteTimeoutHandler(10)));

    return WebClient.builder()
        .clientConnector(new ReactorClientHttpConnector(httpClient))
        .codecs(configurer -> configurer.defaultCodecs()
            .maxInMemorySize(16 * 1024 * 1024)) // 16MB max buffer
        .build();
}

// Connection lifecycle:
// 1. Request arrives → check pool for available connection
// 2. If available → reuse (HTTP keep-alive)
// 3. If not available and pool not full → create new connection
// 4. If pool full → queue request (pendingAcquireTimeout)
// 5. After response → return connection to pool (not closed!)
// 6. Idle connections evicted after maxIdleTime
// 7. All connections closed after maxLifeTime (prevents DNS caching issues)
```

---

## Production Patterns

### Q36: Circuit Breaker with WebFlux (Resilience4j)

```java
@Service
public class ResilientService {
    private final ReactiveCircuitBreaker circuitBreaker;
    private final WebClient webClient;

    public ResilientService(ReactiveCircuitBreakerFactory factory, WebClient webClient) {
        this.circuitBreaker = factory.create("externalService");
        this.webClient = webClient;
    }

    public Mono<Data> fetchData(String id) {
        return circuitBreaker.run(
            webClient.get()
                .uri("/api/data/{id}", id)
                .retrieve()
                .bodyToMono(Data.class)
                .timeout(Duration.ofSeconds(3)),
            throwable -> {
                log.warn("Circuit breaker fallback for {}: {}", id, throwable.getMessage());
                return Mono.just(Data.fallback());
            }
        );
    }
}

// Or using annotations with Reactor return types:
@CircuitBreaker(name = "externalService", fallbackMethod = "fallback")
@TimeLimiter(name = "externalService")
public Mono<Data> fetchData(String id) {
    return webClient.get()
        .uri("/api/data/{id}", id)
        .retrieve()
        .bodyToMono(Data.class);
}

public Mono<Data> fallback(String id, Throwable t) {
    return Mono.just(Data.fallback());
}
```

---

### Q37: Debugging reactive code

```java
// PROBLEM: Reactive stack traces are useless by default
// java.lang.NullPointerException
//   at reactor.core.publisher.FluxMap$MapSubscriber.onNext(FluxMap.java:100)
//   at reactor.core.publisher.FluxFilter$FilterSubscriber.onNext(FluxFilter.java:100)
//   ... (no mention of YOUR code!)

// SOLUTION 1: Hooks.onOperatorDebug() (DEVELOPMENT ONLY - expensive!)
Hooks.onOperatorDebug(); // Captures assembly stack traces
// Now you get:
// Assembly trace from producer [reactor.core.publisher.FluxMap]:
//   at com.example.UserService.findById(UserService.java:42)

// SOLUTION 2: checkpoint() - targeted debugging
Flux.range(1, 10)
    .map(this::riskyOperation)
    .checkpoint("after risky operation")  // Named checkpoint
    .flatMap(this::anotherOperation)
    .checkpoint("after another operation")
    .subscribe();
// On error, shows which checkpoint was last passed

// SOLUTION 3: log() operator
Flux.range(1, 5)
    .log("myFlux", Level.FINE, SignalType.ON_NEXT, SignalType.ON_ERROR)
    .subscribe();
// Logs: onSubscribe, request(n), onNext(value), onComplete/onError

// SOLUTION 4: ReactorDebugAgent (production-safe, Java agent)
// Add: reactor-tools dependency
// In main():
ReactorDebugAgent.init(); // Transforms assembly at class load time
// Much lower overhead than Hooks.onOperatorDebug()

// SOLUTION 5: Metrics on every operator
Flux.range(1, 100)
    .name("my-flux")          // Name for metrics
    .metrics()                // Enables Micrometer metrics
    .subscribe();
// Exposes: reactor.flow.duration, reactor.subscribed, etc.
```

---

### Q38: BlockHound - detecting blocking calls

```java
// BlockHound detects blocking calls on non-blocking threads

// Setup (test scope):
// dependency: io.projectreactor.tools:blockhound

@BeforeAll
static void setup() {
    BlockHound.install();
}

@Test
void detectBlocking() {
    Mono.fromCallable(() -> {
        Thread.sleep(100); // BLOCKING!
        return "data";
    })
    .subscribeOn(Schedulers.parallel()) // parallel = non-blocking scheduler
    .block();
    // Throws: reactor.blockhound.BlockingOperationError:
    //   Blocking call! java.lang.Thread.sleep
}

// Allowed blocking (whitelist):
BlockHound.install(builder -> builder
    .allowBlockingCallsInside("com.example.LegacyService", "oldMethod")
    .allowBlockingCallsInside("io.netty.resolver.dns.DnsNameResolver", "resolve")
);

// Custom blocking detection:
BlockHound.install(builder -> builder
    .markAsBlocking(InputStream.class, "read", "(byte[])int")
    .markAsBlocking(Socket.class, "connect", "(java.net.SocketAddress,int)void")
);
```

---

## Performance

### Q46: WebFlux vs MVC performance comparison

```
Benchmark: REST API, 2 DB calls (50ms each) + 1 HTTP call (100ms)

Scenario 1: Low concurrency (100 concurrent users)
  Spring MVC:   950 req/s, p99=110ms
  Spring WebFlux: 960 req/s, p99=108ms
  → No significant difference at low load

Scenario 2: Medium concurrency (1000 concurrent users)
  Spring MVC:   1900 req/s, p99=520ms (thread pool queuing)
  Spring WebFlux: 9500 req/s, p99=112ms
  → WebFlux 5x throughput, consistent latency

Scenario 3: High concurrency (10000 concurrent users)
  Spring MVC:   1950 req/s, p99=5100ms (severe queuing)
  Spring WebFlux: 45000 req/s, p99=115ms
  → WebFlux 23x throughput, MVC collapses

Scenario 4: CPU-intensive (100ms computation per request)
  Spring MVC:   80 req/s per core
  Spring WebFlux: 75 req/s per core (slightly worse due to reactive overhead)
  → For CPU-bound: MVC is simpler and slightly better

Memory usage at 10K concurrent:
  Spring MVC:   ~10GB (threads) - IMPOSSIBLE without virtual threads
  Spring WebFlux: ~200MB (connection state on heap)
```

---

### Q47: When NOT to use WebFlux

```
1. BLOCKING DEPENDENCIES THAT CAN'T BE REPLACED:
   - JDBC (no reactive driver) → Use R2DBC or Virtual Threads instead
   - Legacy libraries that block
   - File I/O without reactive support

2. SIMPLE CRUD APPLICATIONS:
   - Not I/O bound
   - Low concurrent users (<500)
   - Team unfamiliar with reactive
   - Debugging complexity not justified

3. CPU-INTENSIVE WORKLOADS:
   - Image processing, encryption, ML inference
   - Event loop threads would be blocked
   - Thread-per-request (or virtual threads) better

4. TEAM READINESS:
   - Steep learning curve
   - Debugging is significantly harder
   - Code review requires reactive expertise
   - Testing is more complex

5. EXISTING SPRING MVC APPLICATION:
   - Migration cost is HIGH
   - Not just controller layer - entire stack must be reactive
   - One blocking call ruins the whole benefit
   - Consider: enable virtual threads instead (1-line change)

DECISION MATRIX:
  Java 21+ available? → Virtual Threads (simpler, nearly same performance)
  Need streaming/backpressure? → WebFlux
  All dependencies reactive? → WebFlux is valid
  Any blocking dependency? → DON'T use WebFlux (or wrap carefully)
  New team? → Virtual Threads or traditional MVC
```

---

### Q48: Memory management in reactive streams

```java
// DataBuffer management (prevent leaks!)
// WebFlux uses DataBuffer for request/response bodies
// These are reference-counted (Netty ByteBuf underneath)
// MUST be released or consumed!

// LEAK: Not consuming response body
webClient.get().uri("/api")
    .exchangeToMono(response -> {
        if (response.statusCode().isError()) {
            // BUG: Body not consumed → DataBuffer leak!
            return Mono.error(new RuntimeException("Error"));
        }
        return response.bodyToMono(Data.class);
    });

// FIX: Always consume or release body
webClient.get().uri("/api")
    .exchangeToMono(response -> {
        if (response.statusCode().isError()) {
            return response.bodyToMono(String.class) // Consume body!
                .flatMap(body -> Mono.error(new RuntimeException(body)));
        }
        return response.bodyToMono(Data.class);
    });

// Or use .retrieve() which handles this automatically:
webClient.get().uri("/api")
    .retrieve()
    .onStatus(HttpStatusCode::isError, response ->
        response.bodyToMono(String.class)
            .flatMap(body -> Mono.error(new RuntimeException(body))))
    .bodyToMono(Data.class);

// Monitoring for buffer leaks:
// -Dio.netty.leakDetection.level=PARANOID (development only!)
// Logs: LEAK: ByteBuf.release() was not called before garbage collection
```

---

### Q49: Reactive performance anti-patterns

```java
// ANTI-PATTERN 1: Blocking on event loop
@GetMapping("/data")
public Mono<Data> getData() {
    Data data = blockingService.fetch(); // BLOCKS EVENT LOOP!
    return Mono.just(data);
}
// FIX:
@GetMapping("/data")
public Mono<Data> getData() {
    return Mono.fromCallable(() -> blockingService.fetch())
        .subscribeOn(Schedulers.boundedElastic());
}

// ANTI-PATTERN 2: Excessive flatMap concurrency
Flux.range(1, 100000)
    .flatMap(id -> webClient.get().uri("/api/" + id).retrieve().bodyToMono(Data.class))
    // 256 concurrent HTTP calls! Will overwhelm downstream or exhaust connections!
// FIX:
    .flatMap(id -> fetchData(id), 16) // Limit to 16 concurrent

// ANTI-PATTERN 3: Creating new WebClient per request
@GetMapping("/data")
public Mono<Data> getData() {
    WebClient client = WebClient.create(); // New connection pool each time!
    return client.get().uri("/api").retrieve().bodyToMono(Data.class);
}
// FIX: Inject shared WebClient bean

// ANTI-PATTERN 4: .block() in reactive chain
@GetMapping("/data")
public Mono<Data> getData() {
    User user = userService.findById(id).block(); // BLOCKS!
    return Mono.just(process(user));
}
// FIX: Use flatMap
@GetMapping("/data")
public Mono<Data> getData() {
    return userService.findById(id).map(this::process);
}

// ANTI-PATTERN 5: subscribe() inside reactive chain
@GetMapping("/data")
public Mono<Data> getData() {
    return fetchData()
        .doOnNext(data -> {
            auditService.log(data).subscribe(); // Fire-and-forget inside chain!
            // If audit fails, no one knows. Resources may leak.
        });
}
// FIX: Use flatMap or then()
@GetMapping("/data")
public Mono<Data> getData() {
    return fetchData()
        .flatMap(data -> auditService.log(data).thenReturn(data));
}
```

---

### Q50: Reactive application monitoring

```java
// Micrometer integration with Reactor
// All WebFlux endpoints auto-instrumented with:
// - http.server.requests (timer)
// - reactor.netty.* (connection pool metrics)

// Custom reactive metrics:
@Service
public class OrderService {
    private final MeterRegistry registry;
    
    public Mono<Order> processOrder(Order order) {
        return Mono.just(order)
            .name("order.process")    // Metric name
            .tag("type", order.getType())
            .metrics()                 // Enable metrics for this chain
            .flatMap(this::doProcess);
    }
}

// Key metrics to monitor for reactive apps:
// 1. reactor.netty.connection.provider.active-connections
// 2. reactor.netty.connection.provider.idle-connections
// 3. reactor.netty.connection.provider.pending-connections
// 4. reactor.scheduler.tasks.pending (scheduler queue depth)
// 5. http.server.requests (latency, throughput, errors)
// 6. jvm.buffer.memory.used (direct memory for Netty)
// 7. reactor.flow.duration (per-flow timing)

// Prometheus endpoint exposes all metrics:
management:
  endpoints:
    web:
      exposure:
        include: prometheus, health, metrics
  metrics:
    tags:
      application: ${spring.application.name}
```
