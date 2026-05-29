# Staff Engineer - Part 8: gRPC/Protobuf, GraalVM Native Image, Project Loom
# Advanced topics for Staff/Principal level interviews

---

## gRPC & Protocol Buffers Deep Dive

### Q279: How does gRPC work internally vs REST?

```
REST/JSON:                          gRPC/Protobuf:
┌─────────────┐                     ┌─────────────┐
│ JSON text   │ ~500 bytes          │ Protobuf    │ ~120 bytes (binary)
│ HTTP/1.1    │ text headers        │ HTTP/2      │ binary frames
│ One req/conn│ (or keep-alive)     │ Multiplexed │ many req/single conn
│ No schema   │ OpenAPI optional    │ Strict .proto│ code generation
│ Unary only  │ request-response    │ 4 patterns  │ unary + streaming
└─────────────┘                     └─────────────┘

PERFORMANCE COMPARISON (typical):
- Serialization: Protobuf 3-10x faster than JSON
- Payload size: Protobuf 30-80% smaller
- Latency: gRPC ~2-5ms, REST ~10-50ms (HTTP/2 multiplexing)
- Throughput: gRPC handles 10x more requests per connection
```

### Q280: gRPC Communication Patterns

```protobuf
// service.proto
syntax = "proto3";

service OrderService {
    // 1. Unary (traditional request-response)
    rpc GetOrder(GetOrderRequest) returns (Order);
    
    // 2. Server streaming (one request, stream of responses)
    rpc WatchOrderStatus(WatchRequest) returns (stream OrderStatusUpdate);
    
    // 3. Client streaming (stream of requests, one response)
    rpc UploadOrderBatch(stream Order) returns (BatchResult);
    
    // 4. Bidirectional streaming (both stream)
    rpc OrderChat(stream ChatMessage) returns (stream ChatMessage);
}

message Order {
    string id = 1;
    string user_id = 2;
    repeated OrderItem items = 3;
    OrderStatus status = 4;
    google.protobuf.Timestamp created_at = 5;
    
    // Oneof: only one field set at a time (union type)
    oneof payment {
        CreditCard credit_card = 6;
        BankTransfer bank_transfer = 7;
        Wallet wallet = 8;
    }
}

enum OrderStatus {
    ORDER_STATUS_UNSPECIFIED = 0;
    ORDER_STATUS_CREATED = 1;
    ORDER_STATUS_PAID = 2;
    ORDER_STATUS_SHIPPED = 3;
}

message OrderItem {
    string sku = 1;
    int32 quantity = 2;
    int64 price_cents = 3;  // Use cents, not float!
}
```

### Q281: gRPC Java Server Implementation

```java
// Generated from .proto: OrderServiceGrpc.OrderServiceImplBase

class OrderServiceImpl extends OrderServiceGrpc.OrderServiceImplBase {
    
    // Unary RPC
    @Override
    public void getOrder(GetOrderRequest request, 
                         StreamObserver<Order> responseObserver) {
        try {
            Order order = orderRepository.findById(request.getId());
            if (order == null) {
                responseObserver.onError(Status.NOT_FOUND
                    .withDescription("Order not found: " + request.getId())
                    .asRuntimeException());
                return;
            }
            responseObserver.onNext(order);
            responseObserver.onCompleted();
        } catch (Exception e) {
            responseObserver.onError(Status.INTERNAL
                .withDescription(e.getMessage())
                .withCause(e)
                .asRuntimeException());
        }
    }
    
    // Server Streaming RPC
    @Override
    public void watchOrderStatus(WatchRequest request, 
                                 StreamObserver<OrderStatusUpdate> responseObserver) {
        String orderId = request.getOrderId();
        
        // Subscribe to order status changes
        Disposable subscription = eventBus.subscribe(orderId, event -> {
            OrderStatusUpdate update = OrderStatusUpdate.newBuilder()
                .setOrderId(orderId)
                .setStatus(event.getNewStatus())
                .setTimestamp(Timestamps.fromMillis(System.currentTimeMillis()))
                .build();
            
            responseObserver.onNext(update);
            
            // Complete stream when order is terminal
            if (event.getNewStatus() == OrderStatus.DELIVERED) {
                responseObserver.onCompleted();
            }
        });
        
        // Handle client disconnect
        Context.current().addListener(context -> {
            subscription.dispose();
        }, MoreExecutors.directExecutor());
    }
    
    // Client Streaming RPC
    @Override
    public StreamObserver<Order> uploadOrderBatch(
            StreamObserver<BatchResult> responseObserver) {
        
        List<Order> batch = new ArrayList<>();
        
        return new StreamObserver<Order>() {
            @Override
            public void onNext(Order order) {
                batch.add(order);
                if (batch.size() >= 1000) {
                    flushBatch(batch);
                    batch.clear();
                }
            }
            
            @Override
            public void onCompleted() {
                if (!batch.isEmpty()) flushBatch(batch);
                responseObserver.onNext(BatchResult.newBuilder()
                    .setProcessed(batch.size())
                    .setStatus("SUCCESS")
                    .build());
                responseObserver.onCompleted();
            }
            
            @Override
            public void onError(Throwable t) {
                // Client disconnected or error
                log.error("Batch upload error", t);
            }
        };
    }
}

// Server setup
Server server = ServerBuilder.forPort(9090)
    .addService(new OrderServiceImpl())
    .addService(ProtoReflectionService.newInstance())  // For grpcurl
    .intercept(new AuthInterceptor())         // Authentication
    .intercept(new LoggingInterceptor())      // Logging
    .maxInboundMessageSize(4 * 1024 * 1024)  // 4MB max
    .build()
    .start();
```

### Q282: gRPC Interceptors (Middleware)

```java
// Server-side interceptor (like Spring filters)
class AuthInterceptor implements ServerInterceptor {
    
    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {
        
        // Extract auth token from metadata (like HTTP headers)
        String token = headers.get(
            Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER));
        
        if (token == null || !token.startsWith("Bearer ")) {
            call.close(Status.UNAUTHENTICATED
                .withDescription("Missing or invalid token"), new Metadata());
            return new ServerCall.Listener<>() {};  // No-op listener
        }
        
        // Validate token and propagate user context
        try {
            UserContext user = jwtService.validate(token.substring(7));
            Context ctx = Context.current().withValue(USER_CONTEXT_KEY, user);
            return Contexts.interceptCall(ctx, call, headers, next);
        } catch (Exception e) {
            call.close(Status.UNAUTHENTICATED
                .withDescription("Token validation failed"), new Metadata());
            return new ServerCall.Listener<>() {};
        }
    }
}

// Client-side interceptor (add auth to all outgoing calls)
class ClientAuthInterceptor implements ClientInterceptor {
    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method,
            CallOptions callOptions,
            Channel next) {
        
        return new ForwardingClientCall.SimpleForwardingClientCall<>(
                next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> listener, Metadata headers) {
                headers.put(AUTH_KEY, "Bearer " + tokenProvider.getToken());
                super.start(listener, headers);
            }
        };
    }
}
```

### Q283: gRPC Error Handling & Deadlines

```java
// Error codes (16 standard codes, like HTTP status codes but better)
// OK, CANCELLED, UNKNOWN, INVALID_ARGUMENT, DEADLINE_EXCEEDED,
// NOT_FOUND, ALREADY_EXISTS, PERMISSION_DENIED, RESOURCE_EXHAUSTED,
// FAILED_PRECONDITION, ABORTED, OUT_OF_RANGE, UNIMPLEMENTED,
// INTERNAL, UNAVAILABLE, DATA_LOSS, UNAUTHENTICATED

// Rich error details (Google error model)
StatusRuntimeException error = Status.INVALID_ARGUMENT
    .withDescription("Invalid order")
    .asRuntimeException(trailers);

// With error details:
com.google.rpc.Status status = com.google.rpc.Status.newBuilder()
    .setCode(Code.INVALID_ARGUMENT.getNumber())
    .setMessage("Validation failed")
    .addDetails(Any.pack(BadRequest.newBuilder()
        .addFieldViolations(FieldViolation.newBuilder()
            .setField("quantity")
            .setDescription("Must be positive"))
        .build()))
    .build();

// Deadlines (timeout propagation!)
OrderServiceGrpc.OrderServiceBlockingStub stub = OrderServiceGrpc
    .newBlockingStub(channel)
    .withDeadlineAfter(5, TimeUnit.SECONDS);  // 5 second timeout

try {
    Order order = stub.getOrder(request);
} catch (StatusRuntimeException e) {
    if (e.getStatus().getCode() == Status.Code.DEADLINE_EXCEEDED) {
        // Timeout! Server may still be processing
        log.warn("gRPC call timed out");
    }
}

// IMPORTANT: Deadlines propagate through the call chain!
// Client → ServiceA (5s deadline) → ServiceB (remaining 3s) → ServiceC (remaining 1s)
// Each hop subtracts elapsed time from the deadline
```

### Q284: gRPC Load Balancing & Service Discovery

```java
// Client-side load balancing (recommended for gRPC)
ManagedChannel channel = ManagedChannelBuilder
    .forTarget("dns:///order-service.prod.svc.cluster.local:9090")
    .defaultLoadBalancingPolicy("round_robin")  // or "pick_first"
    .usePlaintext()  // For demo; use TLS in production!
    .build();

// With service discovery (Kubernetes/Consul):
// gRPC resolves DNS to multiple IPs and load-balances across them
// Unlike HTTP/1.1, HTTP/2 multiplexing means one connection per server is enough!

// Connection pooling for high throughput:
class GrpcChannelPool {
    private final List<ManagedChannel> channels;
    private final AtomicInteger counter = new AtomicInteger(0);
    
    GrpcChannelPool(String target, int poolSize) {
        channels = IntStream.range(0, poolSize)
            .mapToObj(i -> ManagedChannelBuilder.forTarget(target)
                .defaultLoadBalancingPolicy("round_robin")
                .build())
            .collect(Collectors.toList());
    }
    
    ManagedChannel getChannel() {
        int idx = counter.getAndIncrement() % channels.size();
        return channels.get(idx);
    }
}
```

---

## GraalVM Native Image Deep Dive

### Q285: What is GraalVM Native Image and how does it work?

```
JVM (Traditional):                   Native Image (AOT):
┌──────────────────┐                 ┌──────────────────┐
│ .class / .jar    │                 │ native binary    │
│ JIT compilation  │                 │ No JVM needed!   │
│ ~100MB memory    │                 │ ~30MB memory     │
│ ~2s startup      │                 │ ~50ms startup    │
│ Peak performance │ ← better long  │ Good performance │
│ after warmup     │   running       │ from first req   │
│ Dynamic features │ all supported   │ Limited dynamic  │
│ (reflection etc) │                 │ features         │
└──────────────────┘                 └──────────────────┘

BUILD PROCESS:
Source → javac → .class → Points-to Analysis → Dead Code Elimination
  → Ahead-of-Time Compilation → Substrate VM → Native Binary

KEY CONCEPT: "Closed-World Assumption"
- Everything reachable must be known at BUILD TIME
- No dynamic class loading at runtime
- Reflection must be pre-configured
- No JIT = no runtime optimization
```

### Q286: GraalVM Limitations and Workarounds

```java
// LIMITATION 1: Reflection (must be declared)
// reflection-config.json:
[
  {
    "name": "com.myapp.model.User",
    "allDeclaredFields": true,
    "allDeclaredMethods": true,
    "allDeclaredConstructors": true
  }
]

// Or use @RegisterForReflection (Quarkus):
@RegisterForReflection
class User {
    String name;
    String email;
}

// LIMITATION 2: Dynamic proxies (JDK Proxy)
// proxy-config.json:
[
  {
    "interfaces": ["com.myapp.service.UserService"]
  }
]

// LIMITATION 3: Resource loading
// resource-config.json:
{
  "resources": {
    "includes": [{"pattern": "application\\.properties"}]
  }
}

// LIMITATION 4: Serialization
// serialization-config.json:
[
  {"name": "com.myapp.model.User"},
  {"name": "java.util.ArrayList"}
]

// AUTO-DETECTION: Use GraalVM tracing agent during tests
// java -agentlib:native-image-agent=config-output-dir=META-INF/native-image \
//      -jar myapp.jar
// Run all code paths → agent records what reflection/proxies/resources are used
```

### Q287: Spring Boot 3 + GraalVM Native

```java
// Spring Boot 3 has first-class native image support via Spring AOT

// Build native image:
// ./mvnw -Pnative native:compile
// or: ./gradlew nativeCompile

// Spring AOT processing (at build time):
// 1. Evaluates @Conditional annotations
// 2. Generates reflection hints
// 3. Generates proxy hints
// 4. Pre-computes bean definitions
// 5. Transforms @Configuration classes to functional style

// Custom hints for your code:
@Configuration
@ImportRuntimeHints(MyHints.class)
class NativeConfig {
}

class MyHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        // Reflection
        hints.reflection().registerType(User.class, 
            MemberCategory.DECLARED_FIELDS, 
            MemberCategory.INVOKE_DECLARED_METHODS);
        
        // Resources
        hints.resources().registerPattern("templates/*.html");
        
        // Proxies
        hints.proxies().registerJdkProxy(UserService.class);
        
        // Serialization
        hints.serialization().registerType(User.class);
    }
}

// Testing native compatibility:
@SpringBootTest
@DisabledInNativeImage  // Skip in native, run in JVM
class SlowIntegrationTest { ... }

@SpringBootTest
class NativeCompatibleTest { ... }  // Runs in both modes

// Performance comparison:
// Spring Boot JVM:    startup=2.5s, memory=256MB, peak throughput=high
// Spring Boot Native: startup=0.05s, memory=64MB, peak throughput=moderate
// Best for: Serverless (Lambda), CLI tools, microservices with many instances
```

### Q288: When NOT to use Native Image

```
USE Native Image when:
✓ Serverless / Lambda (cold start matters)
✓ CLI tools (instant startup)
✓ Kubernetes with aggressive scaling (pods start in ms)
✓ Memory-constrained environments
✓ Microservices with predictable workloads

DON'T use Native Image when:
✗ Long-running services (JIT gives better peak performance)
✗ Heavy reflection/dynamic proxy usage (too many hints needed)
✗ Rapid development (build takes 5-10 minutes)
✗ Libraries not native-compatible (many still aren't)
✗ Need runtime profiling/debugging (limited tooling)
✗ CPU-intensive workloads (JIT optimizes better for hot paths)
```

---

## Project Loom: Virtual Threads Deep Dive

### Q289: Virtual Threads vs Platform Threads - Architecture

```
PLATFORM THREADS (pre-Loom):
┌─────────────────────────────────────────┐
│ Java Thread 1:1 OS Thread               │
│ Stack: 1MB (fixed, reserved at creation)│
│ Context switch: kernel mode (~1-10μs)   │
│ Max practical: ~5,000 threads           │
│ Scheduling: OS scheduler               │
└─────────────────────────────────────────┘

VIRTUAL THREADS (Loom):
┌─────────────────────────────────────────┐
│ Virtual Thread M:N Carrier (Platform)   │
│ Stack: grows/shrinks dynamically        │
│ Context switch: user mode (~200ns)      │
│ Max practical: 1,000,000+ threads       │
│ Scheduling: JVM ForkJoinPool            │
│                                         │
│ When blocked (I/O, sleep, lock):        │
│   → Unmounts from carrier thread        │
│   → Carrier thread picks up next VT     │
│   → When I/O completes, remounts        │
└─────────────────────────────────────────┘

CARRIER POOL (ForkJoinPool):
Carrier-1: [VT-A runs] → VT-A blocks → [VT-B runs] → VT-B blocks → [VT-C runs]
Carrier-2: [VT-D runs] → VT-D blocks → [VT-E runs] → ...
Carrier-3: [VT-F runs] → ...
(Default: #carriers = #CPU cores)
```

### Q290: Virtual Threads Usage Patterns

```java
// Creating virtual threads (Java 21+)
// Method 1: Thread.startVirtualThread
Thread vt = Thread.startVirtualThread(() -> {
    // This runs on a virtual thread
    String result = httpClient.send(request, BodyHandlers.ofString()).body();
    process(result);
});

// Method 2: Thread.ofVirtual()
Thread vt = Thread.ofVirtual()
    .name("worker-", 0)  // worker-0, worker-1, etc.
    .start(() -> doWork());

// Method 3: ExecutorService (RECOMMENDED for production)
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    // Each submitted task gets its own virtual thread!
    List<Future<String>> futures = urls.stream()
        .map(url -> executor.submit(() -> fetchUrl(url)))
        .toList();
    
    List<String> results = futures.stream()
        .map(f -> {
            try { return f.get(); }
            catch (Exception e) { return "error"; }
        })
        .toList();
}

// Method 4: Structured Concurrency (Preview, Java 21+)
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    Subtask<User> userTask = scope.fork(() -> userService.getUser(userId));
    Subtask<List<Order>> ordersTask = scope.fork(() -> orderService.getOrders(userId));
    Subtask<Wallet> walletTask = scope.fork(() -> walletService.getWallet(userId));
    
    scope.join();           // Wait for all
    scope.throwIfFailed();  // Propagate any failure
    
    // All succeeded - combine results
    return new UserProfile(userTask.get(), ordersTask.get(), walletTask.get());
}
// If ANY subtask fails → all others are cancelled! (structured!)

// Spring Boot with Virtual Threads:
// application.properties:
// spring.threads.virtual.enabled=true
// That's it! All request handlers now use virtual threads.
```

### Q291: Virtual Thread Pitfalls and Anti-Patterns

```java
// PITFALL 1: Pinning (virtual thread stuck on carrier)
// Happens when: synchronized block + blocking I/O inside

synchronized (lock) {
    // BAD! Virtual thread is PINNED to carrier thread
    // Other virtual threads can't use this carrier!
    result = httpClient.send(request, BodyHandlers.ofString());
}

// FIX: Use ReentrantLock instead of synchronized
private final ReentrantLock lock = new ReentrantLock();

lock.lock();
try {
    result = httpClient.send(request, BodyHandlers.ofString());
} finally {
    lock.unlock();
}
// ReentrantLock is virtual-thread-friendly (no pinning!)

// PITFALL 2: Thread-local abuse (memory per VT)
// With 1M virtual threads, each ThreadLocal copy = OOM!
private static final ThreadLocal<byte[]> BUFFER = 
    ThreadLocal.withInitial(() -> new byte[64 * 1024]);  // 64KB × 1M = 64GB OOM!

// FIX: Use ScopedValue (Java 21 preview) or pool resources
private static final ScopedValue<RequestContext> CONTEXT = ScopedValue.newInstance();

ScopedValue.runWhere(CONTEXT, new RequestContext(user, traceId), () -> {
    // CONTEXT.get() available within this scope
    processRequest();
});

// PITFALL 3: Pooling virtual threads (defeats the purpose!)
// BAD: 
ExecutorService pool = Executors.newFixedThreadPool(200);  // Platform threads!
// With virtual threads, don't pool! Create millions freely.
// GOOD:
ExecutorService vte = Executors.newVirtualThreadPerTaskExecutor();

// PITFALL 4: CPU-bound work on virtual threads
// Virtual threads shine for I/O-bound work (HTTP calls, DB queries)
// CPU-bound work should still use platform thread pools:
ExecutorService cpuPool = Executors.newFixedThreadPool(Runtime.getRuntime().availableProcessors());
// Only I/O work benefits from virtual threads!

// PITFALL 5: Monitoring - thread dumps show millions of threads
// Use: jcmd <pid> Thread.dump_to_file -format=json threads.json
// New format shows virtual thread grouping
```

### Q292: Virtual Threads with Spring Boot and Database Access

```java
// Spring Boot 3.2+ with virtual threads
@SpringBootApplication
class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }
}
// application.yml:
// spring:
//   threads:
//     virtual:
//       enabled: true

// IMPORTANT: Connection pool sizing changes with virtual threads!
// Before (platform threads): 200 threads → pool size 200 connections
// After (virtual threads): 1M VTs but still only 20 DB connections!
// WHY: Database connections are the bottleneck, not threads

// HikariCP config for virtual threads:
// spring:
//   datasource:
//     hikari:
//       maximum-pool-size: 20        # Database connection limit
//       connection-timeout: 30000    # VTs wait (don't timeout immediately)

// The magic: 1000 concurrent requests arrive
// → 1000 virtual threads created (instant, free)
// → 1000 VTs compete for 20 DB connections
// → 980 VTs suspended (unmounted) while waiting for connection
// → As connections return to pool, waiting VTs resume
// → All 1000 requests served (just with higher latency)

// Compare to platform threads:
// → 200 thread pool (can't create more)
// → 800 requests queued, some timeout!

// WebClient vs RestTemplate with virtual threads:
// BEFORE LOOM: Use WebClient (non-blocking) for high concurrency
// AFTER LOOM: RestTemplate is fine again! (blocking but on virtual threads)
@Service
class OrderClient {
    private final RestTemplate restTemplate;  // Perfectly fine with VTs!
    
    Order getOrder(String id) {
        // This blocks the virtual thread (not the carrier!)
        return restTemplate.getForObject("/orders/" + id, Order.class);
    }
}
```

### Q293: Structured Concurrency Patterns

```java
// Pattern 1: Fan-out with first success (ShutdownOnSuccess)
<T> T race(List<Callable<T>> tasks) throws Exception {
    try (var scope = new StructuredTaskScope.ShutdownOnSuccess<T>()) {
        for (Callable<T> task : tasks) {
            scope.fork(task);
        }
        scope.join();
        return scope.result();  // First successful result, others cancelled
    }
}

// Use case: Query multiple replicas, return fastest response
String data = race(List.of(
    () -> queryReplica1(key),
    () -> queryReplica2(key),
    () -> queryReplica3(key)
));

// Pattern 2: Fan-out with all success (ShutdownOnFailure)
record UserDashboard(User user, List<Order> orders, Wallet wallet) {}

UserDashboard loadDashboard(String userId) throws Exception {
    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        var user = scope.fork(() -> userService.get(userId));
        var orders = scope.fork(() -> orderService.list(userId));
        var wallet = scope.fork(() -> walletService.get(userId));
        
        scope.join().throwIfFailed();
        return new UserDashboard(user.get(), orders.get(), wallet.get());
    }
    // If any fails, ALL are cancelled immediately!
}

// Pattern 3: Custom scope (e.g., collect all results, even partial failures)
class CollectingScope<T> extends StructuredTaskScope<T> {
    private final List<T> results = Collections.synchronizedList(new ArrayList<>());
    private final List<Throwable> errors = Collections.synchronizedList(new ArrayList<>());
    
    @Override
    protected void handleComplete(Subtask<? extends T> subtask) {
        switch (subtask.state()) {
            case SUCCESS -> results.add(subtask.get());
            case FAILED -> errors.add(subtask.exception());
        }
    }
    
    List<T> results() { return results; }
    List<Throwable> errors() { return errors; }
}

// Pattern 4: Timeout with virtual threads
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    var task = scope.fork(() -> slowService.call());
    
    scope.joinUntil(Instant.now().plusSeconds(5));  // 5s timeout
    scope.throwIfFailed();
    
    return task.get();
}
```

### Q294: ScopedValues (Replacing ThreadLocal for Virtual Threads)

```java
// Problem: ThreadLocal + 1M virtual threads = OOM
// Solution: ScopedValue (Java 21, Preview)

// Immutable, inheritable, automatically cleaned up
private static final ScopedValue<User> CURRENT_USER = ScopedValue.newInstance();
private static final ScopedValue<String> TRACE_ID = ScopedValue.newInstance();

// Set value for a scope
void handleRequest(HttpRequest request) {
    User user = authenticate(request);
    String traceId = UUID.randomUUID().toString();
    
    ScopedValue.runWhere(CURRENT_USER, user, 
        ScopedValue.runWhere(TRACE_ID, traceId, () -> {
            processRequest(request);
        })
    );
    // Values automatically gone after scope exits!
}

// Access in nested code (no passing through parameters!)
void processRequest(HttpRequest request) {
    User user = CURRENT_USER.get();  // Available!
    log.info("[{}] Processing for user: {}", TRACE_ID.get(), user.getName());
    
    orderService.createOrder(request.body());
}

void createOrder(OrderRequest req) {
    User user = CURRENT_USER.get();  // Still available in deeper calls!
    // ...
}

// ThreadLocal vs ScopedValue:
// ThreadLocal: mutable, per-thread copy, manual cleanup, memory leak risk
// ScopedValue: immutable, per-scope, automatic cleanup, zero overhead when not used
```

### Q295: Virtual Threads Performance Characteristics

```java
// Benchmark: 10,000 concurrent HTTP calls

// Platform threads (traditional):
// - Pool size: 200 (OS can't handle more)
// - Total time: ~50 seconds (10000/200 * 1s per call)
// - Memory: ~200MB (200 threads × 1MB stack)

// Virtual threads:
// - All 10,000 launch immediately
// - Total time: ~10 seconds (10000 concurrent, 1s per call, limited by server)
// - Memory: ~50MB (virtual thread stacks grow/shrink dynamically)

// When virtual threads DON'T help:
// 1. CPU-bound work (no I/O to yield at)
// 2. Contended synchronized blocks (pinning)
// 3. Native method calls (pinning)
// 4. Very short tasks (scheduling overhead > benefit)

// Detecting pinning issues:
// -Djdk.tracePinnedThreads=full  (logs when pinning occurs)
// -Djdk.tracePinnedThreads=short (just stack trace)

// Output when pinning detected:
// Thread[#14,ForkJoinPool-1-worker-1,5,CarrierThreads]
//     java.base/java.lang.VirtualThread$VThreadContinuation.onPinned(...)
//     com.myapp.Service.process(Service.java:42) <== PINNED here!
```

---

## Protobuf Wire Format Internals

### Q296: How does Protobuf encode data?

```
// Varint encoding (variable-length integer):
// Small numbers use fewer bytes!
// 1 byte:  0-127
// 2 bytes: 128-16383
// 3 bytes: 16384-2097151

// Example: field number 1, type int32, value 150
// Wire format: 08 96 01
//   08 = (field_number=1 << 3) | wire_type=0 (varint)
//   96 01 = 150 in varint encoding
//     0x96 = 1001 0110 → MSB=1 (more bytes), value = 001 0110
//     0x01 = 0000 0001 → MSB=0 (last byte), value = 000 0001
//     Combined: 000 0001 ++ 001 0110 = 10010110 = 150

// Wire types:
// 0: Varint (int32, int64, uint32, uint64, sint32, sint64, bool, enum)
// 1: 64-bit (fixed64, sfixed64, double)
// 2: Length-delimited (string, bytes, embedded messages, packed repeated)
// 5: 32-bit (fixed32, sfixed32, float)

// WHY PROTOBUF IS SMALL:
// JSON: {"user_id": 12345, "name": "John"}  → 35 bytes
// Proto: 08 B9 60 12 04 4A 6F 68 6E        → 9 bytes (74% smaller!)
// - No field names (just field numbers)
// - No quotes, colons, braces
// - Varint encoding for integers
// - No base64 for binary data
```

### Q297: Protobuf Schema Evolution Rules

```protobuf
// SAFE changes (backward + forward compatible):
// ✓ Add new fields (old code ignores unknown fields)
// ✓ Remove fields (but NEVER reuse the field number!)
// ✓ Rename fields (wire format uses numbers, not names)
// ✓ Change int32 ↔ int64, uint32 ↔ uint64 (compatible varints)
// ✓ Change string ↔ bytes (if valid UTF-8)

// UNSAFE changes (BREAKING):
// ✗ Change field number
// ✗ Change wire type (e.g., int32 → string)
// ✗ Change singular ↔ repeated
// ✗ Reuse a deleted field number

// BEST PRACTICE: Reserve deleted field numbers forever
message User {
    reserved 2, 15, 9 to 11;      // Never reuse these!
    reserved "old_name", "temp";   // Never reuse these names!
    
    string id = 1;
    // field 2 was 'name' - DELETED, reserved
    string email = 3;
    int32 age = 4;
}
```

---

## Interview Questions: gRPC vs REST Decision Framework

### Q298: When to choose gRPC vs REST?

```
Choose gRPC when:
├── Internal service-to-service communication
├── High throughput / low latency requirements
├── Streaming data (real-time updates, file transfer)
├── Strong API contract enforcement needed
├── Polyglot environment (auto-generated clients)
└── Binary data transfer (no base64 overhead)

Choose REST when:
├── Public APIs (browsers, curl-friendly)
├── Simple CRUD operations
├── Team unfamiliar with Protobuf
├── Need human-readable request/response
├── Caching important (HTTP caching built-in)
└── Third-party integrations (universally understood)

HYBRID (common in production):
├── External API: REST/JSON (gateway)
├── Internal: gRPC (service mesh)
└── Gateway translates: gRPC-JSON transcoding
    (google.api.http annotation in .proto)
```

