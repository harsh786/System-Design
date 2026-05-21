# Top 200 Java, JVM, Concurrency, and Spring Interview Question Bank

Purpose: prepare for senior Java backend and architect interviews where the interviewer expects practical depth, not definition-level answers. Use this bank with `05-java-jvm-primary-backend-stack.md`.

How to use:

1. Answer each question out loud in 3-5 minutes.
2. For every concurrency, JVM, GC, or Spring question, include failure modes and production debugging signals.
3. For architect-level answers, connect the concept to latency, throughput, memory, correctness, operability, and scale.
4. Revisit weak questions by building small code examples, profiling them, and explaining the observed behavior.

## Category Map

| Category | Range | What It Trains |
|---|---:|---|
| Java fundamentals, OOP, and language evolution | 1-20 | Core language mastery, design clarity, modern Java features |
| JVM runtime, memory, class loading, and JIT | 21-40 | Runtime internals, performance reasoning, object lifecycle |
| Garbage collection and memory diagnostics | 41-60 | GC selection, heap tuning, pause analysis, leak investigation |
| Java Memory Model, visibility, and atomicity | 61-80 | Correct concurrent reasoning and safe publication |
| Threads, synchronization, locks, and coordination | 81-100 | Locks, latches, semaphores, monitors, deadlock prevention |
| Executors, pools, scheduling, and virtual threads | 101-120 | Thread pool design, backpressure, scheduling, Loom-era Java |
| Collections, generics, streams, and functional Java | 121-140 | Data structures, stream pipelines, parallelism, type safety |
| Async, reactive, WebFlux, IO, and backpressure | 141-160 | Non-blocking design, Reactor, Netty, CompletableFuture patterns |
| Spring Boot, MVC, transactions, and persistence | 161-180 | Enterprise backend design and correctness |
| Production Java, observability, testing, and architecture | 181-200 | Troubleshooting, profiling, resilience, production readiness |

## 1. Java Fundamentals, OOP, and Language Evolution

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 1 | Explain the difference between JDK, JRE, JVM, bytecode, and class files. | Compilation flow, runtime responsibilities, portability, JIT execution. |
| 2 | What happens from `javac` compilation to method execution inside the JVM? | Bytecode, class loading, verification, interpretation, JIT compilation, profiling. |
| 3 | Explain OOP pillars in Java with examples where each can be misused. | Encapsulation, abstraction, inheritance, polymorphism, composition tradeoffs. |
| 4 | How do method overloading and overriding differ? | Compile-time vs runtime binding, covariant returns, access rules, exceptions. |
| 5 | What is the `equals` and `hashCode` contract, and what breaks when it is violated? | Reflexive/symmetric/transitive/consistent/null, hash collections, mutability risk. |
| 6 | Compare `==`, `equals`, `Objects.equals`, and reference identity. | Primitive vs reference comparison, null safety, identity semantics. |
| 7 | Why are Java strings immutable? | Security, interning, hash caching, thread safety, memory tradeoffs. |
| 8 | Explain `String`, `StringBuilder`, and `StringBuffer`. | Immutability, synchronization, performance, when each is appropriate. |
| 9 | What is the difference between `final`, `finally`, and `finalize`? | Language keyword, exception cleanup, deprecated finalization, alternatives. |
| 10 | Explain Java access modifiers and package-private design. | Public/protected/private/default, API boundaries, module encapsulation. |
| 11 | How do interfaces, abstract classes, default methods, and static interface methods differ? | State, constructor rules, multiple inheritance of behavior, compatibility. |
| 12 | What are records and when should they not be used? | Shallow immutability, value-carrier intent, generated methods, invariants. |
| 13 | What are sealed classes and how do they help architecture? | Restricted hierarchy, exhaustive pattern matching, domain modeling. |
| 14 | Explain enums beyond constants. | Singleton safety, fields/methods, strategy enum, serialization behavior. |
| 15 | What are annotations and how are they processed? | Runtime vs compile retention, reflection, annotation processors, Spring usage. |
| 16 | What is reflection, and what are its risks? | Runtime inspection, performance, security, encapsulation, framework use. |
| 17 | Explain Java modules and why many services still do not use them deeply. | JPMS, strong encapsulation, migration friction, classpath compatibility. |
| 18 | What changed in modern Java releases that matters for backend engineers? | Records, sealed classes, switch expressions, text blocks, virtual threads, pattern matching. |
| 19 | How do exceptions work in Java, and when should you use checked vs unchecked exceptions? | Stack unwinding, checked contracts, runtime failures, domain errors. |
| 20 | What makes an object immutable, and how do you design immutable classes correctly? | Final fields, defensive copies, no setters, safe publication, nested mutability. |

## 2. JVM Runtime, Memory, Class Loading, and JIT

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 21 | Explain JVM memory areas. | Heap, stack, metaspace, code cache, native memory, thread stacks. |
| 22 | What is stored on the stack vs heap? | Frames, local variables, references, objects, escape analysis nuance. |
| 23 | Explain object layout in memory. | Header, mark word, class pointer, fields, alignment, compressed oops. |
| 24 | What is metaspace and how is it different from PermGen? | Native memory, class metadata, classloader leaks, tuning implications. |
| 25 | How does class loading work? | Loading, linking, verification, preparation, resolution, initialization. |
| 26 | Explain parent delegation in class loaders. | Bootstrap/platform/application loaders, isolation, override prevention. |
| 27 | When can classloader leaks happen? | App servers, static references, ThreadLocal, JDBC drivers, logging frameworks. |
| 28 | What is bytecode verification? | Type safety, stack maps, security, invalid bytecode rejection. |
| 29 | How does JIT compilation improve performance? | Hot methods, profiling, C1/C2, tiered compilation, deoptimization. |
| 30 | What is method inlining and why can it improve performance? | Call overhead removal, optimization scope, polymorphism limits. |
| 31 | Explain escape analysis and scalar replacement. | Allocation elimination, stack allocation misconception, synchronization elimination. |
| 32 | What are safepoints? | JVM coordination, GC pauses, biased lock revocation legacy, diagnostics. |
| 33 | What is the code cache, and what happens when it fills? | Compiled methods, performance degradation, flushing, sizing. |
| 34 | Explain warm-up in Java services. | JIT profiling, caches, connection pools, class loading, benchmark pitfalls. |
| 35 | How do you read JVM startup and runtime flags? | `java -XX`, ergonomics, container awareness, explicit vs default settings. |
| 36 | What is container-aware JVM behavior? | CPU/memory limits, heap percentage flags, cgroup awareness, risk of OOMKill. |
| 37 | Explain heap sizing tradeoffs. | Throughput, pause time, allocation rate, headroom, container memory. |
| 38 | What is native memory tracking? | JVM native areas, direct buffers, threads, metaspace, diagnosis approach. |
| 39 | What is direct memory and how can it cause production issues? | NIO buffers, Netty, off-heap allocation, `MaxDirectMemorySize`, leaks. |
| 40 | How would you diagnose a Java service that is slow only after running for hours? | Heap growth, GC, JIT deopt, leaks, thread contention, external dependency latency. |

## 3. Garbage Collection and Memory Diagnostics

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 41 | Explain generational garbage collection. | Young/old generations, allocation rate, promotion, survivor spaces. |
| 42 | What are minor, major, mixed, and full GC events? | Collection scope, triggers, pause implications, log interpretation. |
| 43 | Compare Serial, Parallel, G1, ZGC, and Shenandoah. | Throughput, pause targets, heap size, latency goals, operational fit. |
| 44 | How does G1 GC work at a high level? | Regions, remembered sets, young/mixed collections, pause target, humongous objects. |
| 45 | When would you consider ZGC? | Large heaps, low pauses, CPU tradeoff, supported JDK versions. |
| 46 | What causes frequent young GC? | Allocation rate, small young gen, object churn, batch sizes. |
| 47 | What causes full GC in production? | Promotion failure, humongous allocation, metadata pressure, explicit GC. |
| 48 | Explain stop-the-world pauses. | Safepoints, root scanning, pause-sensitive workloads, measurement. |
| 49 | What is allocation rate and why is it important? | Bytes/sec, GC pressure, object churn, performance tuning. |
| 50 | How do you analyze GC logs? | Pause time, frequency, cause, heap before/after, promotion, tail latency. |
| 51 | What is a memory leak in Java if GC exists? | Reachability, unintended references, caches, listeners, ThreadLocal. |
| 52 | How do you investigate `OutOfMemoryError: Java heap space`? | Heap dump, dominator tree, retained size, leak suspects, traffic pattern. |
| 53 | How do you investigate `OutOfMemoryError: Metaspace`? | Classloader leak, dynamic proxies, redeploys, metadata growth. |
| 54 | How do you investigate `OutOfMemoryError: Direct buffer memory`? | NIO/Netty buffers, off-heap tracking, leak detector, direct memory flags. |
| 55 | What is a heap dump and how do you use it? | Capture timing, MAT/VisualVM, dominators, retained heap, sensitive data caution. |
| 56 | What are weak, soft, phantom references, and reference queues? | Reachability levels, cache risks, cleanup patterns, modern alternatives. |
| 57 | Why can large caches harm GC? | Retained heap, promotion, eviction, stale entries, cardinality control. |
| 58 | What is object pooling, and why is it usually harmful in modern Java? | GC efficiency, stale state risk, contention, valid use for scarce resources. |
| 59 | How do finalizers and cleaners affect GC? | Delayed cleanup, extra lifecycle, deprecated finalization, resource safety. |
| 60 | How would you tune GC for a low-latency service? | SLO-first, collector choice, heap sizing, allocation reduction, logs, load testing. |

## 4. Java Memory Model, Visibility, and Atomicity

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 61 | What problem does the Java Memory Model solve? | Visibility, ordering, atomicity, compiler/CPU reordering, portable semantics. |
| 62 | Explain happens-before relationships. | Program order, monitor lock, volatile, thread start/join, transitivity. |
| 63 | What does `volatile` guarantee and what does it not guarantee? | Visibility, ordering, no compound atomicity, safe flags, counters pitfall. |
| 64 | Why is `i++` not thread-safe? | Read-modify-write, races, atomic classes, synchronization. |
| 65 | Explain safe publication. | Final fields, volatile references, locks, static initialization, concurrent collections. |
| 66 | Why are final fields special in the memory model? | Initialization safety, immutable objects, constructor escape risk. |
| 67 | What is instruction reordering and when can it break code? | Compiler/CPU optimization, data races, double-checked locking history. |
| 68 | Explain double-checked locking and the correct Java implementation. | Volatile singleton field, lazy init, alternatives with holder pattern. |
| 69 | What is false sharing? | Cache lines, independent hot fields, padding, `LongAdder`, performance symptoms. |
| 70 | What is CAS and how does it support lock-free algorithms? | Compare-and-swap, retry loops, atomicity, CPU support, contention. |
| 71 | What is the ABA problem? | Value changes away and back, stamped references, versioning. |
| 72 | Compare `AtomicInteger`, `LongAdder`, and synchronized counters. | Contention, exact reads, memory cost, throughput tradeoffs. |
| 73 | What is `VarHandle` and when might it be used? | Low-level access modes, atomics, library/framework internals. |
| 74 | What is data race freedom? | Correct synchronization, undefined-like surprising behavior, reasoning model. |
| 75 | Can a properly synchronized program still be slow? | Contention, lock granularity, blocking, context switching, cache effects. |
| 76 | What is thread confinement? | Local variables, single-thread ownership, actor/event-loop model, avoiding sharing. |
| 77 | Explain `ThreadLocal` and its memory leak risk. | Per-thread storage, thread pool reuse, cleanup with `remove`, context propagation. |
| 78 | What is publication through a concurrent collection? | Happens-before via collection operations, visibility of inserted objects. |
| 79 | How do you design a thread-safe cache? | Safe publication, eviction, atomic loading, stampede control, permission-aware keys. |
| 80 | How do you prove a concurrent class is correct? | Invariants, synchronization policy, happens-before, tests plus stress tools. |

## 5. Threads, Synchronization, Locks, and Coordination

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 81 | Explain the Java thread lifecycle. | New, runnable, blocked, waiting, timed waiting, terminated, scheduler nuance. |
| 82 | Compare `Thread`, `Runnable`, and `Callable`. | Return values, exceptions, execution ownership, executor integration. |
| 83 | What is interruption and how should code handle it? | Cooperative cancellation, blocking APIs, restore interrupt flag, cleanup. |
| 84 | What are daemon threads? | JVM exit behavior, background work risk, resource cleanup. |
| 85 | What does `synchronized` do internally? | Monitor enter/exit, mutual exclusion, visibility, reentrancy. |
| 86 | Compare synchronized instance methods, static methods, and blocks. | Lock object, class lock, scope, lock granularity. |
| 87 | Explain `wait`, `notify`, and `notifyAll`. | Monitor ownership, condition queues, spurious wakeups, loop checks. |
| 88 | Why is `notifyAll` often safer than `notify`? | Multiple conditions, missed wakeups, liveness vs efficiency tradeoff. |
| 89 | What is a mutex? | Mutual exclusion concept, Java monitor/lock implementations, critical sections. |
| 90 | Compare `synchronized` and `ReentrantLock`. | Explicit lock/unlock, fairness, interruptible lock, `tryLock`, conditions. |
| 91 | How does `ReentrantLock` fairness work? | FIFO tendency, throughput cost, starvation avoidance, scheduling caveats. |
| 92 | What is a `Condition` and how is it different from monitor wait/notify? | Multiple wait sets, explicit locks, await/signal, producer-consumer design. |
| 93 | Explain `ReadWriteLock`. | Multiple readers, exclusive writer, read-heavy workloads, writer starvation. |
| 94 | Explain `StampedLock`. | Optimistic reads, stamps, validation, non-reentrancy, pitfalls. |
| 95 | What is `CountDownLatch`, and when is it useful? | One-shot gate, startup coordination, await/countDown, cannot reset. |
| 96 | Compare `CountDownLatch`, `CyclicBarrier`, and `Phaser`. | One-shot vs reusable vs dynamic parties, batch coordination. |
| 97 | What is `Semaphore` and how does it control concurrency? | Permits, throttling, fairness, resource pools, rate-like limits. |
| 98 | What is `Exchanger` and where can it be used? | Pairwise handoff, pipelines, rare but useful coordination. |
| 99 | Explain deadlock, livelock, and starvation. | Conditions, examples, detection, prevention through ordering/timeouts. |
| 100 | How would you debug a production deadlock? | Thread dump, monitor ownership, `jstack`, JFR, mitigation and prevention. |

## 6. Executors, Pools, Scheduling, and Virtual Threads

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 101 | Why should production code prefer executors over manually creating threads? | Lifecycle, pooling, backpressure, naming, metrics, shutdown. |
| 102 | Explain `Executor`, `ExecutorService`, and `ScheduledExecutorService`. | Abstraction levels, submit/execute, futures, scheduling. |
| 103 | How does `ThreadPoolExecutor` work? | Core/max size, queue, keep-alive, thread factory, rejection handler. |
| 104 | How do queue choices affect thread pool behavior? | Unbounded, bounded, synchronous queue, memory risk, latency. |
| 105 | Explain rejection policies. | Abort, caller-runs, discard, discard-oldest, custom backpressure. |
| 106 | How do you size a thread pool for CPU-bound vs IO-bound work? | CPU cores, wait time, blocking ratio, saturation testing, separate pools. |
| 107 | What is thread pool starvation? | Blocking tasks occupying workers, nested submissions, deadlock patterns. |
| 108 | How do you shut down an executor safely? | `shutdown`, `awaitTermination`, `shutdownNow`, interruption, draining. |
| 109 | How does `ScheduledThreadPoolExecutor` work? | Delayed tasks, fixed-rate vs fixed-delay, exception handling, drift. |
| 110 | Compare fixed-rate and fixed-delay scheduling. | Start-time cadence vs completion gap, overlap risk, long task behavior. |
| 111 | What happens when a scheduled task throws an exception? | Future completion, repeated task suppression, logging wrappers. |
| 112 | Explain `ForkJoinPool`. | Work stealing, recursive tasks, common pool, blocking caveats. |
| 113 | When should you avoid parallel streams? | Common pool contention, blocking IO, small data, ordering overhead. |
| 114 | How do `Future` and `CompletableFuture` differ? | Blocking get, composition, callbacks, pipelines, exception handling. |
| 115 | What executor does `CompletableFuture.supplyAsync` use by default? | Common ForkJoinPool, custom executor need, production isolation. |
| 116 | How do you add timeout and cancellation to async tasks? | `orTimeout`, `completeOnTimeout`, cancellation limits, cooperative interruption. |
| 117 | What are virtual threads? | Lightweight threads, blocking style, carrier threads, high-concurrency IO. |
| 118 | What is pinning in virtual threads? | Blocking while holding monitor/native call, carrier capture, mitigation. |
| 119 | When should you not use virtual threads? | CPU-bound tasks, limited downstream capacity, thread-local heavy code, pooling mistake. |
| 120 | What is structured concurrency and why does it matter? | Scoped lifetimes, cancellation propagation, failure handling, request-level tasks. |

## 7. Collections, Generics, Streams, and Functional Java

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 121 | Explain the Java Collections Framework hierarchy. | List, Set, Queue, Map, interfaces vs implementations. |
| 122 | How does `HashMap` work internally? | Hashing, buckets, collisions, tree bins, resize, load factor. |
| 123 | Why should mutable keys not be used in hash maps? | Hash changes, lookup failure, contract violation. |
| 124 | How does `ConcurrentHashMap` support concurrency? | Lock striping/bin locking/CAS, weak consistency, no nulls. |
| 125 | Compare `HashMap`, `Hashtable`, `Collections.synchronizedMap`, and `ConcurrentHashMap`. | Thread safety model, locking granularity, performance, legacy concerns. |
| 126 | Compare `ArrayList` and `LinkedList`. | Memory locality, random access, insert/delete reality, iteration performance. |
| 127 | How does `ArrayList` grow? | Backing array, capacity, amortized cost, memory copying. |
| 128 | Compare `HashSet`, `LinkedHashSet`, and `TreeSet`. | Ordering, hashing, red-black tree, comparator consistency. |
| 129 | Compare `HashMap`, `LinkedHashMap`, and `TreeMap`. | Ordering, access-order LRU, sorted keys, complexity. |
| 130 | Explain `PriorityQueue`. | Heap structure, ordering, complexity, not thread-safe. |
| 131 | Compare `ArrayBlockingQueue`, `LinkedBlockingQueue`, `PriorityBlockingQueue`, and `SynchronousQueue`. | Capacity, ordering, handoff, thread pool impact. |
| 132 | What is `CopyOnWriteArrayList` good for? | Read-heavy workloads, snapshot iteration, write cost, memory churn. |
| 133 | Explain fail-fast, fail-safe, and weakly consistent iterators. | Concurrent modification, snapshots, CHM behavior, correctness expectations. |
| 134 | Explain generics and type erasure. | Compile-time safety, runtime erasure, bridge methods, limitations. |
| 135 | What does PECS mean in Java generics? | Producer extends, consumer super, API design, variance. |
| 136 | Explain `Optional` best practices and anti-patterns. | Return type usage, no fields/params usually, avoid `get`, null boundary. |
| 137 | How do Java streams work? | Source, intermediate operations, terminal operation, laziness, pipeline fusion. |
| 138 | Compare `map`, `flatMap`, `filter`, `peek`, and `reduce`. | Transform, flatten, predicate, debugging side effects, associative reduction. |
| 139 | How do collectors like `groupingBy`, `partitioningBy`, and `toMap` work? | Classification, merge function, downstream collectors, duplicate keys. |
| 140 | What makes a stream pipeline safe or unsafe for parallel execution? | Stateless functions, associativity, side effects, ordering, spliterator. |

## 8. Async, Reactive, WebFlux, IO, and Backpressure

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 141 | Compare synchronous, asynchronous, non-blocking, and reactive programming. | Execution model, blocking behavior, callbacks/futures, demand propagation. |
| 142 | How do you compose multiple `CompletableFuture` calls? | `thenApply`, `thenCompose`, `thenCombine`, `allOf`, error propagation. |
| 143 | How do you handle exceptions in `CompletableFuture` pipelines? | `exceptionally`, `handle`, `whenComplete`, wrapping, fallback strategy. |
| 144 | What are the risks of mixing blocking calls into async code? | Pool exhaustion, latency amplification, hidden serialization, timeouts. |
| 145 | What is Reactive Streams backpressure? | Publisher/subscriber/subscription, demand, bounded queues, overload control. |
| 146 | Explain `Flow.Publisher`, `Subscriber`, `Subscription`, and `Processor`. | Java reactive-streams interfaces, request/cancel protocol, processors. |
| 147 | What are `Mono` and `Flux` in Reactor? | Zero/one vs many values, lazy publishers, completion/error signals. |
| 148 | How is Spring WebFlux different from Spring MVC? | Non-blocking stack, event loop, Reactor types, servlet vs reactive runtime. |
| 149 | What happens when a WebFlux controller returns `Mono<Response>`? | Publisher returned, subscribed by framework, non-blocking response flow. |
| 150 | How do Reactor schedulers work? | Immediate, single, parallel, boundedElastic, publishOn vs subscribeOn. |
| 151 | When should `boundedElastic` be used? | Isolating blocking work, bounded threads/queue, migration bridge. |
| 152 | What is the danger of blocking on Netty event-loop threads? | Event loop starvation, global latency, blocked requests, detection. |
| 153 | Compare `WebClient` and `RestTemplate`. | Reactive/non-blocking vs blocking, streaming, backpressure, migration. |
| 154 | How do you implement retries in reactive pipelines safely? | Retry conditions, backoff, idempotency, jitter, max attempts. |
| 155 | How do you handle timeouts in WebFlux? | Reactor timeout, HTTP client timeouts, fallback, cancellation. |
| 156 | How do you propagate context in reactive code? | Reactor context, MDC challenges, tracing, avoiding ThreadLocal assumptions. |
| 157 | How do you test Reactor pipelines? | StepVerifier, virtual time, deterministic signals, error paths. |
| 158 | Explain Java IO vs NIO. | Streams, channels, buffers, selectors, blocking vs multiplexed IO. |
| 159 | Why is Netty commonly used in high-throughput Java networking? | Event loops, buffers, async pipeline, backpressure, resource management. |
| 160 | How would you design an API gateway in Java for very high concurrency? | Non-blocking IO, backpressure, rate limits, connection pools, timeouts, observability. |

## 9. Spring Boot, MVC, Transactions, and Persistence

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 161 | Explain Spring IoC and dependency injection. | Bean ownership, constructor injection, testability, inversion of control. |
| 162 | What is the Spring bean lifecycle? | Instantiation, dependency injection, post-processors, init/destroy callbacks. |
| 163 | How does Spring Boot auto-configuration work? | Starters, conditional beans, classpath detection, override strategy. |
| 164 | What is the difference between `@Component`, `@Service`, `@Repository`, and `@Controller`? | Stereotypes, scanning, exception translation, semantic intent. |
| 165 | Explain Spring proxy-based AOP. | JDK vs CGLIB proxies, method interception, self-invocation limitation. |
| 166 | Why can `@Transactional` fail silently on self-invocation? | Proxy boundary, internal method calls, refactoring options. |
| 167 | Explain transaction propagation modes. | REQUIRED, REQUIRES_NEW, NESTED, SUPPORTS, NOT_SUPPORTED, correctness use cases. |
| 168 | Explain transaction isolation levels and anomalies. | Dirty read, non-repeatable read, phantom, database-specific behavior. |
| 169 | How do checked and unchecked exceptions affect Spring transaction rollback? | Default rollback rules, rollbackFor, domain exception design. |
| 170 | Explain Spring MVC request lifecycle. | DispatcherServlet, handler mapping, interceptors, argument resolution, view/response. |
| 171 | Compare filters, interceptors, and AOP advice. | Layer, use cases, ordering, request/response access. |
| 172 | How does validation work in Spring Boot APIs? | Bean Validation, `@Valid`, constraint annotations, exception handling. |
| 173 | What is the Spring Security filter chain? | Authentication, authorization, filter order, security context. |
| 174 | Explain OAuth2/JWT resource server validation in Spring. | Token signature, issuer/audience, claims, authorities, clock skew. |
| 175 | What causes N+1 queries in JPA/Hibernate? | Lazy loading, fetch joins, entity graphs, batch fetching, SQL visibility. |
| 176 | Compare optimistic and pessimistic locking in JPA. | Version columns, database locks, contention, retry behavior. |
| 177 | How does Hibernate first-level and second-level cache work? | Persistence context, session scope, shared cache, stale data risk. |
| 178 | How do you tune HikariCP connection pools? | Pool size, timeouts, leak detection, database limits, metrics. |
| 179 | How do you design idempotent REST APIs in Spring? | Idempotency keys, unique constraints, retries, conflict handling. |
| 180 | How do you structure a maintainable Spring Boot service? | Layering, ports/adapters, DTO mapping, transactions, tests, boundaries. |

## 10. Production Java, Observability, Testing, and Architecture

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 181 | How would you troubleshoot high CPU in a Java service? | Thread dump, profiler, JFR, hot methods, GC CPU, runaway loops. |
| 182 | How would you troubleshoot high latency with normal CPU? | Thread states, external calls, locks, pool saturation, tail latency. |
| 183 | How would you troubleshoot thread pool exhaustion? | Active/queued tasks, rejection count, blocking dependency, pool partitioning. |
| 184 | How would you detect and fix a connection pool leak? | Pool metrics, leak detection, missing close, transaction boundaries. |
| 185 | How do you use JFR in production? | Low overhead recording, events, CPU/allocation/lock/GC analysis. |
| 186 | What information do thread dumps provide? | Stack traces, states, locks, deadlocks, blocked/waiting analysis. |
| 187 | What is the difference between metrics, logs, traces, and profiles? | Aggregates, events, request path, code hot spots, correlation. |
| 188 | What Java metrics should every production service expose? | JVM memory, GC, threads, pools, HTTP, DB, queues, error rates. |
| 189 | How do you design logging for high-scale Java services? | Structured logs, correlation IDs, sampling, PII control, async appenders. |
| 190 | How do you benchmark Java code correctly? | JMH, warm-up, dead-code elimination, allocation, realistic workload. |
| 191 | Why are microbenchmarks often misleading? | JVM warm-up, branch prediction, data size, IO exclusion, environment. |
| 192 | How do you test concurrent Java code? | Deterministic design, stress tests, jcstress concept, timeouts, invariants. |
| 193 | How do you test Spring Boot integration behavior? | Testcontainers, real DB, slices, transactions, contract tests. |
| 194 | How do you design graceful shutdown for Java services? | Stop accepting traffic, drain requests, shutdown pools, close resources. |
| 195 | How do you prevent cascading failures in Java microservices? | Timeouts, retries with backoff, circuit breakers, bulkheads, budgets. |
| 196 | How do you choose between blocking, virtual-thread, and reactive architectures? | Team skill, workload, downstream limits, latency, debugging, ecosystem. |
| 197 | How do you handle configuration and secrets safely? | Externalized config, profiles, secret stores, rotation, no logging secrets. |
| 198 | How do you design a Java service for multi-region deployment? | Statelessness, idempotency, data locality, retries, timeouts, observability. |
| 199 | What should a senior Java engineer know about API compatibility? | Binary/source compatibility, semantic versioning, deprecation, serialization. |
| 200 | How would you explain a production incident caused by Java concurrency? | Timeline, root cause, memory model or locking issue, mitigation, permanent fix. |

## Architect-Level Interview Patterns

Use these patterns to turn question answers into senior-level responses:

- Always state the correctness guarantee first: visibility, atomicity, ordering, lifecycle, transaction boundary, or data consistency.
- Connect implementation choices to measurable signals: p99 latency, allocation rate, GC pause, thread count, queue depth, pool saturation, and error budget.
- For concurrency answers, mention cancellation, timeouts, backpressure, shutdown, and observability.
- For JVM answers, mention heap, native memory, threads, classloading, GC logs, JFR, and container limits.
- For Spring answers, mention proxy boundaries, transaction scope, database behavior, connection pools, and production metrics.
- For WebFlux answers, mention Reactor `Mono`/`Flux`, scheduler choice, event-loop safety, backpressure, context propagation, and testing with StepVerifier.

## Additional Hands-On Production and Multithreading Drills

These are common follow-up rounds after theory questions. Interviewers use them to check whether you can move from explanation to real debugging or correct concurrent code.

### Production CPU and Memory Debugging Drills

| Drill | Problem Statement | Strong Answer Must Cover |
|---|---|---|
| P1 | A Java service suddenly reaches 95-100% CPU. Walk through how you debug it in production. | Confirm host/container CPU, compare traffic/error rate, capture thread dumps, use `top -H` or equivalent to find hot native thread IDs, map native thread ID to Java thread, inspect stack, capture JFR/profile, identify hot method, distinguish business loop vs GC CPU vs lock contention vs serialization/compression/encryption. |
| P2 | A Java service has rising memory and eventually crashes. Walk through memory analyzer debugging. | Check heap, non-heap, direct memory, metaspace, thread count, GC logs, heap dump capture, Eclipse MAT/VisualVM/JProfiler dominator tree, retained size, leak suspects, cache growth, listener leaks, `ThreadLocal` leaks, classloader leaks, and safe production dump handling because dumps may contain sensitive data. |
| P3 | CPU is high but thread dumps show many runnable threads doing normal work. What next? | Allocation profiling, async-profiler/JFR CPU flame graph, lock profiling, GC overhead, kernel/system CPU, logging overhead, regex/JSON serialization hotspots, inefficient collections, accidental busy spin. |
| P4 | Memory looks stable, but the container is OOMKilled. What do you inspect? | Native memory, direct buffers, thread stacks, metaspace, code cache, cgroup limits, `MaxRAMPercentage`, `MaxDirectMemorySize`, Native Memory Tracking, Netty buffer leaks, mmap/files, sidecars. |
| P5 | GC pauses are causing p99 latency spikes. How do you prove and fix it? | Correlate latency with GC logs/JFR, check allocation rate, promotion, humongous objects, heap headroom, collector choice, object churn, cache size, payload size, batch size, and load-test before/after tuning. |

### Multithreaded Coding Drills

| Drill | Problem Statement | Required Variants |
|---|---|---|
| C1 | Print even and odd numbers alternately using two threads. Example output: `1 2 3 4 5 6 ... N`, where one thread owns odd numbers and one owns even numbers. | Implement with `synchronized` + `wait/notifyAll`, with `ReentrantLock` + `Condition`, with two `Semaphore` objects, and with an `AtomicInteger` plus coordination. Explain visibility, spurious wakeups, termination, and why busy waiting is not acceptable. |
| C2 | Print even and odd numbers alternately using three or more threads. | Generalize ownership by modulo, preserve exact ordering, avoid missed signals, handle `N` not divisible by thread count, and shut down cleanly. |
| C3 | Print the Fibonacci series with multiple threads while preserving sequence order. Example output: `0 1 1 2 3 5 8 13 ...`. | Variant A: one thread prints even-indexed Fibonacci terms and one prints odd-indexed terms. Variant B: one producer computes terms and multiple printer threads coordinate by index. Variant C: use `BlockingQueue` to separate generation from printing. Explain why sequence dependency limits parallel computation. |
| C4 | Print Fibonacci numbers where each thread computes a partition but output remains ordered. | Use futures or ordered buffers, discuss why naive parallelism can break ordering, handle backpressure if computation outruns printing, and avoid unbounded memory growth. |
| C5 | Build a reusable alternator utility for ordered multithreaded printing. | Support any number of threads, pluggable value generator, cancellation, timeout, exception handling, graceful shutdown, and tests that prove no missing, duplicate, or reordered output. |
| C6 | Implement a custom fixed-size thread pool from scratch. | Use a bounded task queue, worker threads, `execute(Runnable)`, graceful shutdown, immediate shutdown, rejection policy, exception isolation per task, thread naming, metrics hooks, and tests for task completion, rejection, shutdown, and no worker leak. |
| C7 | Implement producer-consumer with multiple producers and consumers. | Use `BlockingQueue` first, then implement the queue manually with `synchronized` + `wait/notifyAll` or `ReentrantLock` + `Condition`. Cover bounded capacity, backpressure, poison pill or close signal, interruption, fairness, ordering expectations, and clean termination. |

### Custom Thread Pool Interview Checklist

A strong custom thread pool answer should include:

- `BlockingQueue<Runnable>` or a custom bounded queue to avoid unbounded memory growth.
- Fixed worker count for the basic version; optional core/max worker design for the advanced version.
- `execute(Runnable task)` that rejects tasks after shutdown and handles queue-full behavior explicitly.
- Worker loop that takes tasks, runs them, catches task exceptions, and keeps the worker alive for the next task.
- Graceful shutdown that stops accepting new tasks and lets queued tasks finish.
- Immediate shutdown that interrupts workers and drains or rejects remaining tasks.
- Rejection policy options: throw, caller-runs, timed offer, discard, or custom handler.
- Observability hooks: active workers, queue depth, completed task count, rejected task count, and thread names.
- Tests for concurrency correctness: all submitted tasks run once, no task runs after rejection, shutdown terminates, interruptions are handled, and no busy waiting occurs.

### Producer-Consumer Interview Checklist

A strong producer-consumer answer should include:

- Bounded buffer to create backpressure when producers outrun consumers.
- Multiple producers and consumers without race conditions, missed signals, or duplicate processing.
- Correct condition loops: producers wait while the queue is full; consumers wait while the queue is empty.
- Clear completion protocol: poison pill, closeable queue, countdown of active producers, or cancellation token.
- Interruption handling that restores interrupt status or exits cleanly.
- Ordering explanation: FIFO per queue, but not necessarily per producer unless explicitly designed.
- Failure handling: consumer exception should not silently kill the system without visibility.
- Metrics: produced count, consumed count, queue depth, blocked producer time, blocked consumer time, and processing error count.

### What Interviewers Look For In These Drills

- Correctness first: no missed numbers, duplicates, deadlocks, livelocks, or out-of-order output.
- Proper condition checks: always use loops around `wait`/`await`, not single `if` checks.
- Clean termination: all threads must exit after the final value without hanging.
- Memory visibility: shared counters and flags must be protected by the same lock, volatile/atomic state, or a proven happens-before relationship.
- No busy waiting: spinning on a shared variable wastes CPU and is usually rejected in senior interviews.
- Production thinking: mention metrics, thread names, timeouts, cancellation, testability, and how the design behaves under failure.
