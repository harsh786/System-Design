# Java, JVM, and Primary Backend Stack

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 6. Languages and Frameworks Roadmap

## Pick One Primary Stack

You need one deep stack and two conversational stacks.

### Primary Stack Option 1: Java + Spring Boot

Master:

- JVM memory: heap, stack, metaspace.
- Garbage collection: G1, ZGC concepts, pause-time trade-offs.
- Java memory model.
- Threads, locks, volatile, synchronized, ReentrantLock.
- ExecutorService, CompletableFuture, virtual threads concepts.
- Collections internals: HashMap, ConcurrentHashMap, ArrayList.
- Spring Boot lifecycle.
- Auto-configuration.
- Dependency injection.
- Spring MVC request lifecycle.
- Spring Security filter chain.
- JPA/Hibernate, transactions, N+1 problem, lazy/eager loading.
- HikariCP/connection pooling.
- Resilience4j.
- Micrometer and OpenTelemetry.
- Testcontainers.

### Primary Stack Option 2: Go

Master:

- Goroutines.
- Channels.
- Context cancellation.
- Interfaces.
- Struct composition.
- Error handling.
- Race detection.
- Worker pools.
- HTTP server internals.
- gRPC.
- Kubernetes/operator ecosystem.

### Primary Stack Option 3: Python

Master:

- FastAPI.
- asyncio.
- multiprocessing vs multithreading.
- GIL basics.
- Pydantic.
- SQLAlchemy.
- Celery.
- PySpark.
- Airflow DAGs.
- Data engineering patterns.

### Primary Stack Option 4: TypeScript/Node.js

Master:

- Event loop.
- Promises and async/await.
- Streams and backpressure.
- Worker threads.
- NestJS.
- Express/Fastify.
- TypeScript type system.
- Memory leaks.
- Observability.

## Architect-Level Framework Questions

Always connect framework internals to:

- Latency.
- Throughput.
- Memory.
- Threading.
- Connection pools.
- Transactions.
- Deployment.
- Debuggability.
- Operational risk.

---


## 20.1 Java and JVM Deep Mastery

Architect-level Java knowledge is not only syntax. You must explain how Java behaves under load, during garbage collection, during lock contention, and during failure.

### JVM Memory and Runtime

- Heap: young generation, old generation, allocation rate, promotion, fragmentation.
- Stack: method frames, local variables, recursion risk, stack overflow.
- Metaspace: class metadata, classloader leaks, dynamic proxy generation.
- Direct memory: Netty, NIO buffers, off-heap caches, native memory tracking.
- Object layout: object header, mark word, compressed ordinary object pointers, alignment.
- Escape analysis: stack allocation and lock elimination opportunities.
- JIT compilation: warmup, profiling, inlining, deoptimization.
- Class loading: bootstrap, platform, application, custom classloaders.

### Garbage Collection

- Generational hypothesis and why allocation is cheap until it is not.
- G1: regions, evacuation, mixed collections, remembered sets, pause-time goals.
- ZGC and Shenandoah concepts: low-pause concurrent compaction.
- Parallel GC vs G1 vs ZGC trade-offs.
- Stop-the-world pauses, safepoints, allocation stalls, promotion failures.
- GC tuning inputs: latency SLO, allocation rate, live-set size, heap size, CPU budget.
- Debugging: GC logs, Java Flight Recorder, heap dumps, allocation profiling.
- Interview rule: always connect GC choice to latency, throughput, memory cost, and operational risk.

### Java Memory Model and Concurrency

- Happens-before relationships.
- Visibility vs atomicity vs ordering.
- `volatile`: visibility and ordering, not compound atomicity.
- `synchronized`: monitor lock, reentrancy, visibility guarantees.
- `ReentrantLock`: explicit lock control, fairness, `tryLock`, interruptible lock waits.
- `ReadWriteLock` and `StampedLock`: read-heavy optimization with complexity trade-offs.
- `AtomicInteger`, `AtomicLong`, `AtomicReference`: CAS and lock-free updates.
- `LongAdder`: high-contention counters through striping.
- `ThreadLocal`: request context and leak risks in pools.
- ExecutorService: bounded queues, rejection policies, graceful shutdown.
- ForkJoinPool: work stealing and CPU-bound parallelism.
- CompletableFuture: async composition, executor selection, exception handling.
- Virtual threads: high-concurrency blocking workloads, pinning risks, and carrier threads.

### Hashing and Collections Internals

- `hashCode` and `equals` contract.
- Hash collision handling and bucket distribution.
- HashMap: array of buckets, load factor, resize, tree bins, fail-fast iterators.
- ConcurrentHashMap: lock striping/bin-level synchronization, CAS, weakly consistent iterators.
- LinkedHashMap: insertion/access order, LRU cache building block.
- TreeMap/TreeSet: red-black tree, ordered operations, comparator correctness.
- ArrayList vs LinkedList: locality, resizing, traversal, insertion trade-offs.
- CopyOnWriteArrayList: read-heavy iteration with expensive writes.
- BlockingQueue types: ArrayBlockingQueue, LinkedBlockingQueue, PriorityBlockingQueue, DelayQueue.
- Interview drill: implement a thread-safe LRU cache and explain lock granularity, eviction, and memory pressure.

### Locking, Mutexes, and Coordination

- Mutex, semaphore, monitor, condition variable, latch, barrier, phaser.
- Deadlock: circular wait, hold-and-wait, no preemption, mutual exclusion.
- Livelock and starvation.
- Lock ordering and timeout-based mitigation.
- Optimistic vs pessimistic locking.
- Spin locks vs blocking locks.
- Compare-and-swap and ABA problem.
- Fencing tokens for distributed locks.
- Redlock cautions and why clock assumptions matter.
- Database locks vs application locks vs distributed locks.

### Java Interview Build Targets

1. Implement `HashMap` with resizing and collision handling.
2. Implement LRU cache using HashMap plus doubly linked list.
3. Implement LFU cache.
4. Implement bounded blocking queue using `ReentrantLock` and `Condition`.
5. Implement thread pool with bounded work queue and rejection policy.
6. Implement rate limiter with token bucket and sliding window.
7. Implement concurrent counter benchmark using `AtomicLong` and `LongAdder`.
8. Implement producer-consumer with graceful shutdown.
9. Debug a simulated GC pause and explain remediation.
10. Build a Spring Boot API and trace one request through servlet thread, connection pool, DB transaction, and telemetry.


