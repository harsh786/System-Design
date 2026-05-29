# Staff Engineer / Architect Level - Advanced Java (Part 2)
# Reactive Programming, Distributed Systems, Zero-Copy I/O, Netty

## Reactive Programming & Backpressure

### Q213: What is Reactive Programming and Project Reactor?

**Answer:**

**Reactive Streams specification** defines 4 interfaces:
```java
public interface Publisher<T> {
    void subscribe(Subscriber<? super T> s);
}

public interface Subscriber<T> {
    void onSubscribe(Subscription s);
    void onNext(T t);          // Receive element
    void onError(Throwable t); // Terminal: error
    void onComplete();         // Terminal: success
}

public interface Subscription {
    void request(long n);  // BACKPRESSURE: request N items
    void cancel();
}

public interface Processor<T, R> extends Subscriber<T>, Publisher<R> { }
```

**Project Reactor (Spring WebFlux default):**
```java
// Mono<T>: 0 or 1 element (like Optional + async)
Mono<User> user = userRepository.findById(1);

// Flux<T>: 0 to N elements (like Stream + async + backpressure)
Flux<Order> orders = orderRepository.findByUserId(1);

// Creation:
Mono<String> mono = Mono.just("hello");
Mono<String> deferred = Mono.defer(() -> Mono.just(compute()));  // Lazy
Mono<String> fromFuture = Mono.fromFuture(completableFuture);
Flux<Integer> flux = Flux.range(1, 100);
Flux<String> fromIterable = Flux.fromIterable(list);
Flux<Long> interval = Flux.interval(Duration.ofSeconds(1));  // Infinite

// Transformation:
Flux<String> names = users.flux()
    .filter(u -> u.isActive())
    .map(User::getName)
    .flatMap(name -> enrichName(name))  // Async transformation
    .take(10)
    .distinct();

// Error handling:
mono.onErrorReturn("default")
    .onErrorResume(ex -> Mono.just("fallback"))
    .retry(3)
    .retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
    .timeout(Duration.ofSeconds(5));

// Combining:
Mono.zip(userMono, ordersMono, profileMono)  // Parallel execution!
    .map(tuple -> new Dashboard(tuple.getT1(), tuple.getT2(), tuple.getT3()));

Flux.merge(source1, source2);      // Interleave (real-time)
Flux.concat(source1, source2);     // Sequential
Flux.zip(source1, source2);        // Pair elements 1:1
```

---

### Q214: What is Backpressure and how does it work?

**Answer:**

**Problem without backpressure:**
```
Fast Producer → → → → → → → → → → → Slow Consumer
                  ↓ ↓ ↓ ↓ ↓ ↓ ↓
              BUFFER OVERFLOW / OOM!
```

**Backpressure = Consumer controls the rate of data flow**
```
Producer ← "I can handle 10 items" ← Consumer
Producer → sends 10 items →          Consumer
Producer ← "I can handle 5 more" ←   Consumer (busy)
Producer → sends 5 items →           Consumer
```

```java
// Reactive Streams backpressure:
Flux.range(1, 1_000_000)
    .subscribe(new BaseSubscriber<Integer>() {
        @Override
        protected void hookOnSubscribe(Subscription subscription) {
            request(10);  // Start with 10 items only
        }
        
        @Override
        protected void hookOnNext(Integer value) {
            process(value);
            request(1);  // Request one more after processing
        }
    });

// Backpressure strategies:
flux.onBackpressureBuffer(1000)   // Buffer up to 1000, then error
flux.onBackpressureBuffer(1000, item -> log.warn("dropped: {}", item))
flux.onBackpressureDrop()         // Drop items when consumer can't keep up
flux.onBackpressureLatest()       // Keep only latest item
flux.onBackpressureError()        // Error signal when overwhelmed

// Operators that manage backpressure:
flux.limitRate(100)               // Prefetch 100, request 75 more at 75% consumed
flux.buffer(100)                  // Collect 100 items into List, emit List
flux.window(100)                  // Collect 100 items into sub-Flux
flux.sample(Duration.ofSeconds(1)) // Emit latest every 1s (drop intermediate)
```

**Schedulers (threading in Reactor):**
```java
// Reactor is non-blocking by default - work happens on subscriber's thread
// Use schedulers to control which thread processes what:

Schedulers.immediate()       // Current thread (no scheduling)
Schedulers.single()          // Single reusable thread
Schedulers.parallel()        // Fixed pool (CPU cores), for CPU work
Schedulers.boundedElastic()  // Elastic pool (bounded), for blocking I/O
Schedulers.fromExecutor(ex)  // Custom executor

// Usage:
flux.publishOn(Schedulers.parallel())    // Downstream runs on parallel scheduler
    .map(this::cpuIntensiveWork)
    .publishOn(Schedulers.boundedElastic())
    .flatMap(this::blockingIOCall)        // Blocking I/O on elastic
    .subscribeOn(Schedulers.boundedElastic()); // Subscription happens on elastic

// publishOn: Affects DOWNSTREAM operators (switch thread mid-pipeline)
// subscribeOn: Affects UPSTREAM subscription signal (where source emits from)
```

---

### Q215: Reactive vs Virtual Threads - When to use which?

**Answer:**

| Aspect | Reactive (WebFlux) | Virtual Threads (Java 21) |
|--------|-------------------|--------------------------|
| Programming model | Functional, non-blocking chain | Imperative, blocking (looks normal!) |
| Learning curve | Steep (Mono/Flux, operators) | Low (same as traditional) |
| Debugging | Hard (async stack traces) | Easy (normal stack traces) |
| Backpressure | Built-in | Manual (BlockingQueue, etc.) |
| Throughput | Excellent | Excellent |
| Ecosystem | WebFlux, R2DBC, WebClient | All existing blocking libraries work |
| Error handling | Operators (onError*) | try-catch (normal!) |
| Code readability | Complex chains | Simple imperative |
| When to choose | Streaming data, backpressure needed, existing reactive codebase | New projects, existing blocking code, simpler model |

```java
// REACTIVE approach:
Mono<User> getUser(int id) {
    return webClient.get()
        .uri("/users/{id}", id)
        .retrieve()
        .bodyToMono(User.class)
        .timeout(Duration.ofSeconds(5))
        .retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
        .onErrorResume(ex -> Mono.just(User.defaultUser()));
}

// VIRTUAL THREADS approach (same result, simpler code):
User getUser(int id) {
    try {
        HttpResponse<String> resp = httpClient.send(
            HttpRequest.newBuilder(URI.create("/users/" + id)).build(),
            HttpResponse.BodyHandlers.ofString()
        );
        return parseUser(resp.body());
    } catch (Exception e) {
        return User.defaultUser();
    }
}
// Called from virtual thread → blocks without blocking OS thread!
```

---

## Distributed Systems Patterns (Java Implementation)

### Q216: Explain CAP Theorem and its practical implications.

**Answer:**

```
CAP Theorem: A distributed system can only guarantee 2 of 3:

C (Consistency): Every read receives the most recent write
A (Availability): Every request receives a response (success/failure)
P (Partition Tolerance): System continues to operate despite network splits

┌─────────────────────────────────────────────────────┐
│                                                       │
│              C (Consistency)                           │
│             /           \                             │
│            /             \                            │
│      CP Systems      CA Systems                      │
│    (HBase, MongoDB     (Traditional RDBMS -          │
│     strong mode,       single node only!             │
│     ZooKeeper)         Not practical in              │
│                        distributed systems)          │
│            \             /                            │
│             \           /                             │
│              A (Availability) ──── P (Partition)     │
│                      AP Systems                       │
│                   (Cassandra, DynamoDB,               │
│                    CouchDB, eventual consistency)     │
│                                                       │
└─────────────────────────────────────────────────────┘

// In practice: P is mandatory (networks WILL partition)
// So real choice is: CP or AP

// CP: Block/error when partition occurs (sacrifice availability)
//     Example: ZooKeeper won't serve reads if it can't reach quorum
// AP: Serve stale data during partition (sacrifice consistency)  
//     Example: DynamoDB returns possibly-stale data during partition
```

**PACELC Theorem (extension):**
```
If Partition → choose Availability or Consistency
Else (normal operation) → choose Latency or Consistency

PA/EL: Sacrifice consistency for availability AND latency (DynamoDB, Cassandra)
PC/EC: Always consistent (strongly consistent databases, ZooKeeper)
PA/EC: Available during partition, consistent otherwise (most real systems)
```

---

### Q217: Explain Saga Pattern for distributed transactions.

**Answer:**

```java
// Problem: In microservices, you can't use 2-Phase Commit (2PC) across services
// (too slow, holds locks, not scalable)

// SAGA: Sequence of local transactions with compensating actions

// Order Saga:
// Step 1: Create Order (OrderService)
// Step 2: Reserve Inventory (InventoryService)
// Step 3: Charge Payment (PaymentService)
// Step 4: Ship Order (ShippingService)

// If Step 3 fails:
// Compensate Step 2: Release Inventory
// Compensate Step 1: Cancel Order
// (Each service knows how to "undo" its action)

// CHOREOGRAPHY (event-driven, no central coordinator):
@Service
class OrderService {
    @TransactionalEventListener
    void onOrderCreated(OrderCreatedEvent e) {
        eventBus.publish(new ReserveInventoryCommand(e.getOrderId(), e.getItems()));
    }
    
    @EventListener
    void onPaymentFailed(PaymentFailedEvent e) {
        // Compensating action
        orderRepository.cancel(e.getOrderId());
        eventBus.publish(new ReleaseInventoryCommand(e.getOrderId()));
    }
}

// ORCHESTRATION (central saga coordinator):
class OrderSaga {
    enum State { CREATED, INVENTORY_RESERVED, PAYMENT_CHARGED, SHIPPED, FAILED }
    
    void execute(OrderRequest request) {
        try {
            Order order = orderService.create(request);        // Step 1
            inventoryService.reserve(order.getItems());         // Step 2
            paymentService.charge(order.getTotal());            // Step 3
            shippingService.ship(order);                        // Step 4
        } catch (PaymentException e) {
            inventoryService.release(order.getItems());         // Compensate 2
            orderService.cancel(order.getId());                 // Compensate 1
        } catch (InventoryException e) {
            orderService.cancel(order.getId());                 // Compensate 1
        }
    }
}

// Real-world: Use frameworks like Axon, Temporal, or Camunda
```

---

### Q218: Explain CQRS and Event Sourcing patterns.

**Answer:**

```java
// CQRS (Command Query Responsibility Segregation):
// Separate READ models from WRITE models

// Traditional: Same model for reads and writes
// CQRS: Optimized models for each

// Write Side (Commands):
class CreateOrderCommand {
    String customerId;
    List<OrderItem> items;
}

@Service
class OrderCommandHandler {
    void handle(CreateOrderCommand cmd) {
        // Validate business rules
        // Write to WRITE database (normalized, consistent)
        Order order = Order.create(cmd.customerId, cmd.items);
        writeRepository.save(order);
        // Publish event for read model update
        eventBus.publish(new OrderCreatedEvent(order));
    }
}

// Read Side (Queries):
@Service
class OrderQueryHandler {
    // Read from READ database (denormalized, optimized for queries)
    OrderSummaryDTO getOrderSummary(String orderId) {
        return readRepository.findSummary(orderId);  // Fast, pre-computed view
    }
    
    List<OrderDashboardDTO> getDashboard(String customerId) {
        return readRepository.findDashboard(customerId);  // Materialized view
    }
}

// Event handler updates read model:
@EventListener
void on(OrderCreatedEvent event) {
    // Update denormalized read model (eventual consistency!)
    OrderSummaryView view = new OrderSummaryView(event);
    readModelRepository.save(view);
}

// EVENT SOURCING: Store events, not state
// Instead of: UPDATE orders SET status='shipped' WHERE id=123
// Store: OrderShippedEvent { orderId: 123, timestamp: ..., trackingNo: ... }

class Order {  // Aggregate
    private String id;
    private OrderStatus status;
    private List<OrderItem> items;
    private List<DomainEvent> uncommittedEvents = new ArrayList<>();
    
    // Rebuild state by replaying events:
    static Order rehydrate(List<DomainEvent> history) {
        Order order = new Order();
        for (DomainEvent event : history) {
            order.apply(event);  // Apply each event to rebuild state
        }
        return order;
    }
    
    void ship(String trackingNo) {
        // Validate
        if (status != OrderStatus.PAID) throw new IllegalStateException();
        // Create event (don't mutate state directly!)
        OrderShippedEvent event = new OrderShippedEvent(id, trackingNo);
        apply(event);
        uncommittedEvents.add(event);
    }
    
    private void apply(OrderShippedEvent event) {
        this.status = OrderStatus.SHIPPED;
    }
}

// Benefits of Event Sourcing:
// - Complete audit trail (every state change is recorded)
// - Time travel (rebuild state at any point in time)
// - Event replay (rebuild read models, fix bugs retroactively)
// - Natural fit for CQRS (events drive read model updates)
// - Debugging (replay exact sequence of events that caused bug)

// Challenges:
// - Schema evolution (old events with old formats)
// - Eventual consistency (read model lags behind write)
// - Complexity (more infrastructure needed)
// - Storage growth (use snapshots to avoid replaying all events)
```

---

### Q219: Explain Distributed Locking with Redis/ZooKeeper.

**Answer:**

```java
// PROBLEM: Multiple service instances need exclusive access to shared resource
// Database row lock doesn't work across services

// APPROACH 1: Redis Distributed Lock (Redisson)
RLock lock = redisson.getLock("order-processing-" + orderId);
try {
    // Wait up to 10s to acquire, auto-expire after 30s
    if (lock.tryLock(10, 30, TimeUnit.SECONDS)) {
        try {
            processOrder(orderId);  // Critical section
        } finally {
            lock.unlock();
        }
    }
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
}

// HOW IT WORKS (Redlock algorithm):
// SET resource_name random_value NX PX 30000
// NX = only set if not exists (atomic acquire)
// PX = auto-expire in 30000ms (prevents deadlock if holder crashes)
// random_value = unique per client (ensures only holder can release)

// Release (Lua script for atomicity):
// if redis.call("get", KEYS[1]) == ARGV[1] then
//     return redis.call("del", KEYS[1])
// end
// (Only delete if we still own the lock)

// APPROACH 2: ZooKeeper Distributed Lock (Curator)
InterProcessMutex lock = new InterProcessMutex(client, "/locks/order-" + orderId);
try {
    if (lock.acquire(10, TimeUnit.SECONDS)) {
        try {
            processOrder(orderId);
        } finally {
            lock.release();
        }
    }
} catch (Exception e) {
    // Handle
}

// HOW IT WORKS:
// 1. Create ephemeral sequential znode: /locks/order-123/lock-0000000001
// 2. Get all children of /locks/order-123
// 3. If my znode has lowest sequence number → I have the lock!
// 4. If not → watch the znode with next lower sequence number
// 5. When watched znode deleted → check again (I might have the lock now)
// 6. Ephemeral: If my session dies, znode auto-deleted → lock released!

// COMPARISON:
// Redis: Faster, simpler, but less safe (clock drift, split-brain)
// ZooKeeper: Stronger guarantees, consensus-based, ephemeral nodes
// etcd: Similar to ZooKeeper, uses Raft consensus
```

---

### Q220: Explain Consistent Hashing and its Java implementation.

**Answer:**

```java
// PROBLEM: Distributing data across N servers
// Naive: hash(key) % N → BUT adding/removing server remaps EVERYTHING!

// CONSISTENT HASHING: Only K/N keys remapped on server change

// Concept: Hash ring (0 to 2^32 - 1)
// Each server mapped to position on ring
// Each key mapped to position → assigned to NEXT server clockwise

class ConsistentHash<T> {
    private final TreeMap<Long, T> ring = new TreeMap<>();
    private final int virtualNodes;  // Multiple positions per server
    private final MessageDigest md = MessageDigest.getInstance("MD5");
    
    ConsistentHash(int virtualNodes) {
        this.virtualNodes = virtualNodes;
    }
    
    // Add server with virtual nodes (for even distribution)
    void addNode(T node) {
        for (int i = 0; i < virtualNodes; i++) {
            long hash = hash(node.toString() + "#" + i);
            ring.put(hash, node);
        }
    }
    
    void removeNode(T node) {
        for (int i = 0; i < virtualNodes; i++) {
            long hash = hash(node.toString() + "#" + i);
            ring.remove(hash);
        }
    }
    
    // Find which server owns this key
    T getNode(String key) {
        if (ring.isEmpty()) return null;
        long hash = hash(key);
        // Find first server at or after key's position
        Map.Entry<Long, T> entry = ring.ceilingEntry(hash);
        if (entry == null) {
            entry = ring.firstEntry();  // Wrap around ring
        }
        return entry.getValue();
    }
    
    private long hash(String key) {
        md.reset();
        byte[] digest = md.digest(key.getBytes());
        return ((long)(digest[3] & 0xFF) << 24) |
               ((long)(digest[2] & 0xFF) << 16) |
               ((long)(digest[1] & 0xFF) << 8) |
               (digest[0] & 0xFF);
    }
}

// Usage:
ConsistentHash<String> ch = new ConsistentHash<>(150);  // 150 virtual nodes
ch.addNode("server1");
ch.addNode("server2");
ch.addNode("server3");

String server = ch.getNode("user:12345");  // → "server2"
// Adding server4 only remaps ~1/4 of keys (not all!)

// Virtual nodes: Each physical server has ~150 positions on ring
// This ensures even distribution (without virtual nodes, can be very uneven)
// More virtual nodes = more even distribution but more memory
```

---

## Zero-Copy I/O, Reactor Pattern & Netty Internals

### Q221: Explain Zero-Copy in Java.

**Answer:**

```
// TRADITIONAL FILE TRANSFER (4 copies, 4 context switches):
// 1. read(file_fd, buffer, len)
//    Kernel → User space buffer (copy 1, context switch 1-2)
// 2. write(socket_fd, buffer, len)  
//    User space buffer → Kernel socket buffer (copy 2, context switch 3-4)
// 3. Kernel DMA: disk → kernel buffer (copy 0 - DMA)
// 4. Kernel DMA: socket buffer → NIC (copy 0 - DMA)
// Total: 4 context switches, 2 CPU copies, 2 DMA copies

// ZERO-COPY (sendfile / transferTo):
// File data goes: Disk → Kernel buffer → NIC (never enters user space!)
// 0 CPU copies, 2 DMA copies, 2 context switches
```

```java
// Java Zero-Copy: FileChannel.transferTo()
FileChannel sourceChannel = FileChannel.open(sourcePath, READ);
SocketChannel socketChannel = SocketChannel.open(serverAddress);

// Zero-copy transfer (uses OS sendfile/splice):
sourceChannel.transferTo(0, sourceChannel.size(), socketChannel);
// Data goes directly from file to socket without entering JVM heap!

// Also: FileChannel.transferFrom() for receiving

// Memory-Mapped Files (another zero-copy technique):
MappedByteBuffer mapped = sourceChannel.map(MapMode.READ_ONLY, 0, size);
// File mapped directly into virtual address space
// No read() calls needed - just access memory!

// Netty uses zero-copy via:
// 1. CompositeByteBuf (logical merging without physical copy)
// 2. FileRegion (wraps transferTo for file serving)
// 3. Direct buffers (off-heap, DMA-capable)
```

---

### Q222: Explain the Reactor Pattern and Event Loop.

**Answer:**

```
// Reactor Pattern: Single thread handles thousands of connections via I/O multiplexing

// Traditional: Thread-per-connection
// Client 1 → Thread 1 (blocked on read)
// Client 2 → Thread 2 (blocked on read)
// Client 3 → Thread 3 (blocked on read)
// Problem: 10,000 clients = 10,000 threads = ~10GB RAM + context switch overhead

// Reactor: Single thread + event loop + non-blocking I/O
// ┌─────────────────────────────────────────────────────────┐
// │                    EVENT LOOP                             │
// │                                                           │
// │  Selector.select() ← blocks until I/O events ready      │
// │       │                                                   │
// │       ├── Connection 1 readable → handle read            │
// │       ├── Connection 2 writable → handle write           │
// │       ├── Connection 3 acceptable → accept new conn      │
// │       └── Connection 4 readable → handle read            │
// │                                                           │
// │  ONE thread handles ALL connections (non-blocking!)       │
// └─────────────────────────────────────────────────────────┘
```

```java
// Java NIO Reactor:
class Reactor implements Runnable {
    final Selector selector = Selector.open();
    final ServerSocketChannel serverChannel;
    
    Reactor(int port) throws IOException {
        serverChannel = ServerSocketChannel.open();
        serverChannel.bind(new InetSocketAddress(port));
        serverChannel.configureBlocking(false);
        serverChannel.register(selector, SelectionKey.OP_ACCEPT);
    }
    
    @Override
    public void run() {
        while (!Thread.currentThread().isInterrupted()) {
            selector.select();  // Block until I/O event
            Set<SelectionKey> keys = selector.selectedKeys();
            for (SelectionKey key : keys) {
                if (key.isAcceptable()) accept(key);
                else if (key.isReadable()) read(key);
                else if (key.isWritable()) write(key);
            }
            keys.clear();
        }
    }
    
    void accept(SelectionKey key) throws IOException {
        SocketChannel client = serverChannel.accept();
        client.configureBlocking(false);
        client.register(selector, SelectionKey.OP_READ);
    }
    
    void read(SelectionKey key) throws IOException {
        SocketChannel client = (SocketChannel) key.channel();
        ByteBuffer buffer = ByteBuffer.allocate(1024);
        int bytesRead = client.read(buffer);  // Non-blocking!
        if (bytesRead > 0) {
            buffer.flip();
            processRequest(buffer, key);
        }
    }
}
```

---

### Q223: Explain Netty Architecture and Internals.

**Answer:**

```
// Netty Architecture:
// ┌─────────────────────────────────────────────────────────────────┐
// │                          Channel                                  │
// │   (represents a connection: socket, file, etc.)                  │
// │                                                                   │
// │   ┌──────────────────────────────────────────────────────────┐   │
// │   │                  ChannelPipeline                           │   │
// │   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
// │   │   │ Handler │→│ Handler │→│ Handler │→│ Handler │  │   │
// │   │   │(Decode) │  │(Business│  │(Encode) │  │ (Log)   │  │   │
// │   │   └─────────┘  └─────────┘  └─────────┘  └─────────┘  │   │
// │   │   INBOUND →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→ OUTBOUND      │   │
// │   └──────────────────────────────────────────────────────────┘   │
// │                                                                   │
// └─────────────────────────────────────────────────────────────────┘
//
// ┌─────────────────────────────────────────────────────────────────┐
// │                       EventLoopGroup                              │
// │   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐     │
// │   │EventLoop 0│ │EventLoop 1│ │EventLoop 2│ │EventLoop 3│     │
// │   │(1 thread) │ │(1 thread) │ │(1 thread) │ │(1 thread) │     │
// │   │handles    │ │handles    │ │handles    │ │handles    │     │
// │   │channels   │ │channels   │ │channels   │ │channels   │     │
// │   │[ch1,ch5]  │ │[ch2,ch6]  │ │[ch3,ch7]  │ │[ch4,ch8]  │     │
// │   └───────────┘ └───────────┘ └───────────┘ └───────────┘     │
// └─────────────────────────────────────────────────────────────────┘
```

```java
// Netty Server:
EventLoopGroup bossGroup = new NioEventLoopGroup(1);      // Accept connections
EventLoopGroup workerGroup = new NioEventLoopGroup(4);    // Handle I/O

ServerBootstrap server = new ServerBootstrap()
    .group(bossGroup, workerGroup)
    .channel(NioServerSocketChannel.class)
    .childHandler(new ChannelInitializer<SocketChannel>() {
        @Override
        protected void initChannel(SocketChannel ch) {
            ch.pipeline()
                .addLast(new LengthFieldBasedFrameDecoder(1024, 0, 4))  // Frame decode
                .addLast(new ProtobufDecoder(Request.getDefaultInstance()))  // Protobuf
                .addLast(new BusinessHandler())   // Your logic
                .addLast(new ProtobufEncoder());  // Encode response
        }
    })
    .option(ChannelOption.SO_BACKLOG, 128)
    .childOption(ChannelOption.SO_KEEPALIVE, true)
    .childOption(ChannelOption.TCP_NODELAY, true);

ChannelFuture future = server.bind(8080).sync();
future.channel().closeFuture().sync();

// Key Netty concepts:
// 1. EventLoop: Single thread that owns channels (no synchronization needed!)
// 2. Channel: Connection abstraction (NIO, Epoll, KQueue)
// 3. Pipeline: Chain of handlers (interceptor pattern)
// 4. ByteBuf: Better than ByteBuffer (pool-able, reference counted, composite)
// 5. Promise/Future: Async result with listeners

// Netty ByteBuf advantages over NIO ByteBuffer:
// - Separate read/write indexes (no flip() needed!)
// - Pooled (reduces GC pressure for high-throughput)
// - Reference counted (deterministic deallocation)
// - Composite (merge without copying)
// - Direct and Heap variants
// - Auto-expanding (no BufferOverflowException)
```

---

### Q224: What is Epoll vs NIO Selector and when to use each?

**Answer:**

```java
// NIO Selector (Java standard): Uses OS-level poll/epoll/kqueue
// Netty provides native transport for better performance:

// Linux: Epoll (O(1) for event notification)
EventLoopGroup group = new EpollEventLoopGroup();  // Native Linux
ServerBootstrap b = new ServerBootstrap()
    .group(group)
    .channel(EpollServerSocketChannel.class);  // Native channel

// macOS: KQueue
EventLoopGroup group = new KQueueEventLoopGroup();
// .channel(KQueueServerSocketChannel.class)

// Cross-platform: NIO (fallback)
EventLoopGroup group = new NioEventLoopGroup();
// .channel(NioServerSocketChannel.class)

// WHY native is faster:
// 1. JNI overhead reduced (fewer calls between Java and native)
// 2. Epoll edge-triggered mode (only notified on STATE CHANGE, not level)
// 3. No need to rebuild interest set on each select()
// 4. Additional options: TCP_FASTOPEN, SO_REUSEPORT, SPLICE
// 5. ~30% better throughput in benchmarks

// Connection handling scale:
// select():  O(N) per call - scans all FDs (bad for 100K+ connections)
// poll():    O(N) - same as select but no FD limit
// epoll():   O(1) per event - only returns ready FDs (excellent for 100K+)
// io_uring:  O(1) - even better (zero-copy, submission queue) - Java support via Netty incubator
```

---

## Distributed Tracing & Observability

### Q225: Explain Distributed Tracing with OpenTelemetry in Java.

**Answer:**

```java
// Distributed Tracing: Track requests across microservices

// Concepts:
// TRACE: End-to-end journey of a request (has unique traceId)
// SPAN: One unit of work within a trace (has spanId, parentSpanId)
// CONTEXT PROPAGATION: Pass traceId/spanId between services (via HTTP headers)

// Example trace:
// [Trace: abc123]
// └── [Span: Gateway (100ms)]
//     ├── [Span: UserService.getUser (30ms)]
//     │   └── [Span: PostgreSQL query (10ms)]
//     └── [Span: OrderService.getOrders (50ms)]
//         ├── [Span: MongoDB query (20ms)]
//         └── [Span: CacheService.lookup (5ms)]

// OpenTelemetry Java Agent (zero-code instrumentation):
// java -javaagent:opentelemetry-javaagent.jar \
//      -Dotel.service.name=order-service \
//      -Dotel.exporter.otlp.endpoint=http://collector:4317 \
//      -jar myapp.jar

// Manual instrumentation:
OpenTelemetry otel = GlobalOpenTelemetry.get();
Tracer tracer = otel.getTracer("com.myapp.OrderService");

Span span = tracer.spanBuilder("processOrder")
    .setSpanKind(SpanKind.INTERNAL)
    .setAttribute("order.id", orderId)
    .startSpan();

try (Scope scope = span.makeCurrent()) {
    // This code is traced
    Order order = fetchOrder(orderId);
    span.setAttribute("order.amount", order.getAmount());
    processPayment(order);  // Child span created automatically (if instrumented)
} catch (Exception e) {
    span.setStatus(StatusCode.ERROR, e.getMessage());
    span.recordException(e);
    throw e;
} finally {
    span.end();
}

// Context propagation (automatic with agent, manual example):
// Service A → HTTP call → Service B
// Headers injected: traceparent: 00-<traceId>-<spanId>-01
// Service B extracts context and creates child span

// Metrics (RED method):
// Rate: requests per second
// Errors: error rate
// Duration: latency percentiles (p50, p95, p99)

// Spring Boot Actuator + Micrometer + OpenTelemetry:
// application.yml:
// management.tracing.sampling.probability: 1.0  # 100% sampling (dev only!)
// management.otlp.tracing.endpoint: http://collector:4318/v1/traces
```

---

### Q226: What are the key metrics for a Java microservice in production?

**Answer:**

```java
// THE FOUR GOLDEN SIGNALS (Google SRE):
// 1. Latency: Time to serve a request (p50, p95, p99)
// 2. Traffic: Demand on the system (requests/sec)
// 3. Errors: Rate of failed requests
// 4. Saturation: How "full" the system is (CPU, memory, queue depth)

// JVM-specific metrics to monitor:
// MEMORY:
//   - jvm.memory.used (heap, non-heap)
//   - jvm.memory.committed
//   - jvm.memory.max
//   - jvm.gc.pause (duration, count)
//   - jvm.gc.memory.promoted (bytes promoted to old gen)
//   - jvm.gc.live.data.size (old gen after GC)

// THREADS:
//   - jvm.threads.live
//   - jvm.threads.peak
//   - jvm.threads.states (RUNNABLE, BLOCKED, WAITING, TIMED_WAITING)

// CONNECTION POOLS:
//   - hikaricp.connections.active
//   - hikaricp.connections.idle
//   - hikaricp.connections.pending (threads waiting for connection)
//   - hikaricp.connections.timeout (connection acquisition timeouts)

// HTTP:
//   - http.server.requests (count, sum, max per URI, method, status)
//   - http.server.requests.p99
//   - http.client.requests (outgoing calls)

// BUSINESS:
//   - orders.created (counter)
//   - orders.processing.time (histogram)
//   - payment.failures (counter with tags: reason)

// Micrometer example:
@Service
class OrderService {
    private final Counter orderCounter;
    private final Timer orderTimer;
    
    OrderService(MeterRegistry registry) {
        this.orderCounter = registry.counter("orders.created", "type", "online");
        this.orderTimer = registry.timer("orders.processing.time");
    }
    
    Order createOrder(OrderRequest req) {
        return orderTimer.record(() -> {
            Order order = process(req);
            orderCounter.increment();
            return order;
        });
    }
}
```

---

## ClassLoader Leaks & Hot Deployment

### Q227: What causes ClassLoader leaks and how to fix them?

**Answer:**

```java
// ClassLoader leak: ClassLoader cannot be GC'd because something still references it
// Results in: Metaspace/PermGen OOM after multiple hot deployments

// ROOT CAUSE: ClassLoader is retained if ANY of its loaded classes is retained

// Class retention chain:
// Static field in loaded class → Class object → ClassLoader → ALL loaded classes
// If ANYTHING references a Class loaded by this ClassLoader → entire ClassLoader stays!

// Common leak patterns:

// 1. ThreadLocal holding class from webapp ClassLoader
class WebAppClass {
    static ThreadLocal<WebAppClass> local = new ThreadLocal<>();
    // Thread pool thread holds reference → Class → ClassLoader → ALL classes!
}
// FIX: Always remove ThreadLocals on undeploy

// 2. JDBC Driver registration
// DriverManager holds reference to driver loaded by webapp ClassLoader
// FIX: Explicitly deregister in context destroy listener
@Override
public void contextDestroyed(ServletContextEvent event) {
    Enumeration<Driver> drivers = DriverManager.getDrivers();
    while (drivers.hasMoreElements()) {
        Driver driver = drivers.nextElement();
        if (driver.getClass().getClassLoader() == getClass().getClassLoader()) {
            DriverManager.deregisterDriver(driver);
        }
    }
}

// 3. Shutdown hooks referencing webapp classes
Runtime.getRuntime().addShutdownHook(new Thread(() -> {
    // This lambda captures enclosing class → ClassLoader leak!
}));

// 4. Static caches in libraries (common in frameworks)
// Logging frameworks, serialization, reflection caches
// FIX: Use weak references, clear caches on undeploy

// 5. Timer/Scheduler threads
Timer timer = new Timer();
timer.schedule(new TimerTask() { ... }, 0, 1000);
// TimerTask holds reference to its ClassLoader
// FIX: Cancel all timers on undeploy

// DETECTION:
// 1. Heap dump after undeploy → search for ClassLoader instances
// 2. Find GC root path (what's keeping ClassLoader alive?)
// 3. Tools: Eclipse MAT with "Duplicate Classes" analysis

// PREVENTION:
// - Use LeakPreventor libraries (classloader-leak-prevention)
// - Always cleanup on undeploy (listeners, threads, caches)
// - Avoid static fields referencing mutable state
// - Modern approach: Use containers (Docker) → just kill the process!
```

---

### Q228: Explain ByteBuddy and runtime bytecode generation.

**Answer:**

```java
// ByteBuddy: Modern bytecode generation library
// Used by: Mockito, Hibernate, Jackson, Spring (alternatives to CGLIB)

// 1. Create a subclass (like CGLIB proxy):
Class<?> dynamicType = new ByteBuddy()
    .subclass(Object.class)
    .method(ElementMatchers.named("toString"))
    .intercept(FixedValue.value("Hello ByteBuddy!"))
    .make()
    .load(getClass().getClassLoader())
    .getLoaded();

Object instance = dynamicType.getDeclaredConstructor().newInstance();
System.out.println(instance.toString());  // "Hello ByteBuddy!"

// 2. Method interception (AOP-like):
Class<? extends UserService> proxyClass = new ByteBuddy()
    .subclass(UserService.class)
    .method(ElementMatchers.any())
    .intercept(MethodDelegation.to(new LoggingInterceptor()))
    .make()
    .load(UserService.class.getClassLoader())
    .getLoaded();

class LoggingInterceptor {
    @RuntimeType
    public static Object intercept(@Origin Method method,
                                    @AllArguments Object[] args,
                                    @SuperCall Callable<?> superCall) throws Exception {
        long start = System.nanoTime();
        try {
            return superCall.call();  // Invoke original method
        } finally {
            long duration = System.nanoTime() - start;
            log.info("{} took {}ns", method.getName(), duration);
        }
    }
}

// 3. Java Agent with ByteBuddy (runtime class modification):
public class MyAgent {
    public static void premain(String args, Instrumentation inst) {
        new AgentBuilder.Default()
            .type(ElementMatchers.nameStartsWith("com.myapp"))
            .transform((builder, type, classLoader, module, domain) ->
                builder.method(ElementMatchers.any())
                       .intercept(MethodDelegation.to(TimingInterceptor.class))
            )
            .installOn(inst);
    }
}
// Every method in com.myapp.* is now instrumented with timing!

// 4. Mockito uses ByteBuddy:
// when(mock.method()) → ByteBuddy subclass overrides method
// → Interceptor records expected behavior
// → On actual call, interceptor returns recorded value
```

---

### Q229: What is AppCDS (Application Class-Data Sharing)?

**Answer:**

```bash
# AppCDS: Share class metadata across JVM instances
# Reduces startup time and memory footprint

# Step 1: Create class list (dump classes loaded by app)
java -Xshare:off -XX:DumpLoadedClassList=classes.lst -jar app.jar

# Step 2: Create shared archive from class list
java -Xshare:dump -XX:SharedClassListFile=classes.lst \
     -XX:SharedArchiveFile=app-cds.jsa -jar app.jar

# Step 3: Use shared archive on startup
java -Xshare:on -XX:SharedArchiveFile=app-cds.jsa -jar app.jar

# Benefits:
# - 30-50% faster startup (classes pre-loaded from memory-mapped archive)
# - Lower memory footprint (shared across multiple JVM instances on same host)
# - Container-friendly (build archive in Docker image layer)

# Java 13+: Dynamic CDS (automatic archive creation)
java -XX:ArchiveClassesAtExit=app-cds.jsa -jar app.jar
# Next run automatically uses the archive

# Java 19+: Default archive improved (more classes pre-cached)

# For containers (Dockerfile):
# Build stage: create archive
# Run stage: use archive
# FROM eclipse-temurin:21 as builder
# RUN java -XX:ArchiveClassesAtExit=/app/cds.jsa -jar app.jar --exit-after-init
# FROM eclipse-temurin:21
# COPY --from=builder /app/cds.jsa /app/cds.jsa
# CMD java -XX:SharedArchiveFile=/app/cds.jsa -jar app.jar
```

---

### Q230: Explain CRaC (Coordinated Restore at Checkpoint) for instant startup.

**Answer:**

```java
// CRaC: Checkpoint a running JVM → Restore instantly (millisecond startup!)
// Like VM snapshot but for JVM process

// How it works:
// 1. Application starts normally, warms up (JIT, caches loaded)
// 2. Checkpoint: JVM state serialized to files (memory, threads, FDs)
// 3. Restore: JVM process recreated from files (instant!)

// Startup time: 2-10 seconds → ~50 milliseconds!

// API (application must handle resource re-acquisition):
import org.crac.*;

class MyApp implements Resource {
    
    @Override
    public void beforeCheckpoint(Context<? extends Resource> context) {
        // Called before checkpoint - close external resources!
        connectionPool.close();
        fileHandles.closeAll();
        scheduledTasks.cancel();
    }
    
    @Override
    public void afterRestore(Context<? extends Resource> context) {
        // Called after restore - reconnect everything!
        connectionPool.reconnect();
        fileHandles.reopen();
        scheduledTasks.reschedule();
        // Refresh certificates, tokens, etc.
    }
}

// Registration:
Core.getGlobalContext().register(myApp);

// Trigger checkpoint (from within app or via jcmd):
// jcmd <pid> JDK.checkpoint

// Restore:
// java -XX:CRaCRestoreFrom=/path/to/checkpoint

// Challenges:
// - Open file descriptors must be re-acquired
// - Network connections are stale (must reconnect)
// - Random seeds/timestamps need refresh
// - Security tokens may be expired
// - PID changes (not same process)

// Best for: Serverless (AWS Lambda), scale-to-zero, autoscaling
// Supported by: Azul Zulu, OpenJDK CRaC project
```

---

## Production Thread Pool Tuning

### Q231: How to size thread pools for production?

**Answer:**

```java
// FORMULA (Brian Goetz - Java Concurrency in Practice):
// Optimal threads = N_cpu * U_cpu * (1 + W/C)
//
// N_cpu = Number of CPU cores (Runtime.getRuntime().availableProcessors())
// U_cpu = Target CPU utilization (0.0 to 1.0, typically 0.8)
// W/C   = Ratio of Wait time to Compute time

// CPU-BOUND tasks (computation, no I/O):
// W/C ≈ 0 → threads = N_cpu * U_cpu = N_cpu (or N_cpu + 1)
// Example: 8 cores → 8-9 threads
ExecutorService cpuPool = Executors.newFixedThreadPool(
    Runtime.getRuntime().availableProcessors());

// I/O-BOUND tasks (HTTP calls, DB queries):
// W/C is high (e.g., waiting 90% of time → W/C = 9)
// threads = 8 * 0.8 * (1 + 9) = 64 threads
// Or empirically: measure W/C ratio and calculate

// MIXED workload:
// Separate pools for CPU and I/O tasks!
ExecutorService cpuPool = new ThreadPoolExecutor(
    8, 8, 0L, TimeUnit.MILLISECONDS,        // Fixed CPU pool
    new LinkedBlockingQueue<>(100));

ExecutorService ioPool = new ThreadPoolExecutor(
    20, 100, 60L, TimeUnit.SECONDS,          // Elastic I/O pool
    new SynchronousQueue<>(),                 // Direct handoff
    new CallerRunsPolicy());                  // Backpressure

// LITTLE'S LAW for service thread pools:
// L = λ * W
// L = average number of threads busy
// λ = arrival rate (requests/second)
// W = average processing time (seconds)
//
// Example: 1000 req/s, 100ms average latency
// L = 1000 * 0.1 = 100 threads needed (minimum!)
// Add headroom: 100 * 1.5 = 150 threads
// Set max pool size to 150

// PRODUCTION RECOMMENDATIONS:
// 1. Always use bounded queues (prevent OOM under load!)
// 2. Set meaningful thread names (for debugging)
// 3. Monitor queue depth, active threads, rejection count
// 4. Use CallerRunsPolicy for natural backpressure
// 5. Different pools for different workload types
// 6. Start conservative, tune based on metrics
// 7. Use virtual threads for I/O-heavy workloads (Java 21+)

// Monitoring thread pool health:
ThreadPoolExecutor pool = (ThreadPoolExecutor) executor;
int activeCount = pool.getActiveCount();
int queueSize = pool.getQueue().size();
long completedTasks = pool.getCompletedTaskCount();
int poolSize = pool.getPoolSize();
int largestPoolSize = pool.getLargestPoolSize();

// Alert if:
// - queueSize > 80% capacity (approaching saturation)
// - activeCount == maximumPoolSize for extended time (fully saturated)
// - rejectedExecutionCount > 0 (tasks being dropped!)
// - queueSize growing over time (consumer too slow)
```

---

### Q232: What is Structured Concurrency and why does it matter for architects?

**Answer:**

```java
// Problem with unstructured concurrency:
void handleRequest() {
    Future<A> futureA = executor.submit(() -> fetchA());  // Fire and forget
    Future<B> futureB = executor.submit(() -> fetchB());  // Fire and forget
    
    // What if handleRequest() throws before getting results?
    // → futureA and futureB are ORPHANED (still running, wasting resources)
    // → No way to cancel them (we lost the references)
    // → Thread dump shows threads with no clear owner
    // → Resource leak!
}

// Structured Concurrency (Java 21 Preview):
// GUARANTEE: Subtask lifetime bounded by scope lifetime
Response handleRequest() throws Exception {
    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        // Fork subtasks (bounded by scope)
        Subtask<User> user = scope.fork(() -> fetchUser());
        Subtask<Order> order = scope.fork(() -> fetchOrder());
        
        scope.join();           // Wait for all subtasks
        scope.throwIfFailed();  // Propagate any failure
        
        return new Response(user.get(), order.get());
    }
    // GUARANTEED: When scope closes:
    // - All subtasks are completed or cancelled
    // - No orphaned threads
    // - Clean stack traces (parent-child relationship visible)
    // - If one fails, others are cancelled immediately
}

// WHY THIS MATTERS FOR ARCHITECTS:
// 1. Observability: Thread dumps show task hierarchy (which request owns which threads)
// 2. Cancellation: Cancel a request → all its subtasks automatically cancelled
// 3. Error handling: Child failure propagates cleanly to parent
// 4. Resource management: No resource leaks from orphaned tasks
// 5. Reasoning: Concurrent code is as structured as sequential code
// 6. Debugging: No more mystery threads running with no owner

// Custom scope policies:
// ShutdownOnFailure: If ANY subtask fails, cancel all others
// ShutdownOnSuccess: When FIRST subtask succeeds, cancel all others
// Custom: Implement your own policy (e.g., require majority success)
```

---

## Summary: Staff Engineer / Architect Must-Know Checklist

| Category | Key Topics |
|----------|-----------|
| **JVM Internals** | Object layout, CompressedOops, Safepoints, TTSP, JIT tiers, Deoptimization |
| **Memory Deep** | Escape Analysis, Scalar Replacement, Write Barriers, Card Table, SATB, Colored Pointers |
| **Performance** | False Sharing, @Contended, Cache Lines, NUMA, Branch Prediction, Mechanical Sympathy |
| **Lock-Free** | CAS, Treiber Stack, Michael-Scott Queue, ABA Problem, Lock-Free vs Wait-Free |
| **GC Internals** | G1 regions, RSets, ZGC colored pointers, Load Barriers, concurrent relocation |
| **Off-Heap** | Unsafe, Panama FFM, Arena, Direct ByteBuffer, memory-mapped files |
| **Containers** | cgroup awareness, CPU throttling, memory sizing, ActiveProcessorCount, GC tuning |
| **I/O** | Zero-Copy, transferTo, Reactor pattern, Epoll vs Poll, io_uring |
| **Netty** | EventLoop, Channel, Pipeline, ByteBuf pooling, native transport |
| **Reactive** | Mono/Flux, Backpressure, Schedulers, vs Virtual Threads trade-offs |
| **Distributed** | CAP/PACELC, Saga, CQRS, Event Sourcing, Consistent Hashing, Distributed Locks |
| **Observability** | OpenTelemetry, Distributed Tracing, 4 Golden Signals, Micrometer |
| **Startup** | AppCDS, CRaC, GraalVM native image, class loading optimization |
| **Pool Tuning** | Little's Law, W/C ratio, bounded queues, monitoring, HikariCP internals |
| **Modern Java** | Virtual Threads, Structured Concurrency, Scoped Values, Foreign Memory |

