# Java Concurrency

Concurrency means multiple tasks make progress during overlapping time periods. Java supports concurrency through threads, locks, executors, atomic variables, concurrent collections, and asynchronous APIs.

For LLD, concurrency matters when designing:

- caches
- connection pools
- rate limiters
- job schedulers
- pub-sub systems
- booking/reservation flows
- producer-consumer queues
- singleton services

## Process Versus Thread

| Concept | Meaning |
|---|---|
| Process | Independent running program with its own memory |
| Thread | Execution path inside a process |

Threads in the same process share heap memory. That is powerful and dangerous.

## Creating Threads

Using `Runnable`:

```java
Runnable task = () -> System.out.println(Thread.currentThread().getName());
Thread thread = new Thread(task);
thread.start();
thread.join();
```

Important methods:

| Method | Meaning |
|---|---|
| `start()` | Starts a new thread and calls `run()` on that thread |
| `run()` | Task body. Calling directly does not create a new thread |
| `join()` | Current thread waits for another thread to finish |
| `sleep(ms)` | Current thread pauses |
| `interrupt()` | Requests a thread to stop/wake from blocking |
| `isInterrupted()` | Checks interrupt flag |
| `currentThread()` | Returns current running thread |

## Runnable Versus Callable

| Type | Returns result | Throws checked exception |
|---|---:|---:|
| `Runnable` | No | No |
| `Callable<V>` | Yes | Yes |

```java
Callable<Integer> task = () -> 42;
```

Use `Callable` with `ExecutorService` when you need a result.

## Race Condition

A race condition occurs when correctness depends on timing between threads.

Bad:

```java
counter++;
```

This is not atomic. It roughly does:

1. read current value
2. add one
3. write new value

Two threads can interleave and lose updates.

## synchronized

`synchronized` protects a critical section using an object's monitor.

```java
class SafeCounter {
    private int value;

    synchronized void increment() {
        value++;
    }

    synchronized int get() {
        return value;
    }
}
```

`synchronized` provides:

- mutual exclusion: one thread enters at a time
- visibility: changes become visible to later synchronized access on the same monitor

## synchronized Block

```java
private final Object lock = new Object();

void update() {
    synchronized (lock) {
        // critical section
    }
}
```

Use a private lock object instead of locking on public objects like strings or `this` when external code should not share your lock.

## volatile

`volatile` gives visibility, not atomicity.

```java
class StopFlag {
    private volatile boolean stopped;

    void stop() {
        stopped = true;
    }

    boolean stopped() {
        return stopped;
    }
}
```

`volatile` is good for flags and published references. It is not enough for compound operations like increment.

Bad:

```java
volatile int count;
count++; // still not atomic
```

## Atomic Classes

Atomic classes provide lock-free thread-safe operations.

```java
AtomicInteger counter = new AtomicInteger();
counter.incrementAndGet();
counter.addAndGet(5);
counter.compareAndSet(6, 10);
```

Common atomic classes:

- `AtomicInteger`
- `AtomicLong`
- `AtomicBoolean`
- `AtomicReference<T>`
- `LongAdder` for high-contention counters

## Lock And ReentrantLock

`ReentrantLock` is an explicit lock.

```java
Lock lock = new ReentrantLock();
lock.lock();
try {
    // critical section
} finally {
    lock.unlock();
}
```

Use it when you need features beyond `synchronized`:

- timed lock attempts
- interruptible lock acquisition
- fairness option
- multiple conditions

## ReadWriteLock

`ReadWriteLock` allows many readers or one writer.

```java
ReadWriteLock rw = new ReentrantReadWriteLock();
rw.readLock().lock();
try {
    // read
} finally {
    rw.readLock().unlock();
}
```

Use when reads are frequent and writes are rare.

## wait, notify, notifyAll

These methods belong to `Object` and must be called while holding that object's monitor.

```java
synchronized (lock) {
    while (!condition) {
        lock.wait();
    }
}
```

Always use `while`, not `if`, because a thread can wake up even when the condition is still false.

In modern code, `BlockingQueue`, `CountDownLatch`, `Semaphore`, or `Condition` is usually clearer than raw wait/notify.

## ExecutorService

Thread creation is expensive. `ExecutorService` manages thread pools.

```java
ExecutorService executor = Executors.newFixedThreadPool(4);
Future<Integer> future = executor.submit(() -> 42);
Integer result = future.get();
executor.shutdown();
```

Common factory methods:

| Method | Meaning |
|---|---|
| `newFixedThreadPool(n)` | Fixed number of worker threads |
| `newSingleThreadExecutor()` | One worker, sequential execution |
| `newCachedThreadPool()` | Creates threads as needed, reuses idle ones |
| `newScheduledThreadPool(n)` | Delayed and periodic tasks |
| `newVirtualThreadPerTaskExecutor()` | Virtual thread per task in modern Java |

In production, prefer explicit `ThreadPoolExecutor` configuration when you need bounded queues and rejection policies.

## Future

`Future<V>` represents a result that may be available later.

Important methods:

| Method | Meaning |
|---|---|
| `get()` | Wait for result |
| `get(timeout, unit)` | Wait with timeout |
| `cancel(boolean)` | Attempt cancellation |
| `isDone()` | Completed or cancelled |
| `isCancelled()` | Cancelled |

Limitation: `Future` is not convenient for chaining multiple async stages.

## CompletableFuture

`CompletableFuture` supports async composition.

```java
CompletableFuture<String> future = CompletableFuture
    .supplyAsync(() -> "user")
    .thenApply(String::toUpperCase)
    .exceptionally(ex -> "fallback");
```

Important methods:

| Method | Meaning |
|---|---|
| `supplyAsync` | Run supplier asynchronously |
| `runAsync` | Run task asynchronously without result |
| `thenApply` | Transform result |
| `thenAccept` | Consume result |
| `thenCompose` | Chain dependent async operation |
| `thenCombine` | Combine independent async results |
| `allOf` | Wait for all |
| `anyOf` | Wait for any |
| `exceptionally` | Recover from failure |
| `handle` | Handle success or failure |
| `join` | Get result, wraps exceptions unchecked |

## Concurrent Collections

| Class | Use |
|---|---|
| `ConcurrentHashMap` | Concurrent key-value store |
| `ConcurrentLinkedQueue` | Non-blocking concurrent queue |
| `CopyOnWriteArrayList` | Read-heavy list with snapshot iteration |
| `BlockingQueue` | Producer-consumer coordination |
| `ConcurrentSkipListMap` | Concurrent sorted map |
| `ConcurrentSkipListSet` | Concurrent sorted set |

## BlockingQueue

Producer-consumer example:

```java
BlockingQueue<String> queue = new ArrayBlockingQueue<>(10);
queue.put("job");
String job = queue.take();
```

Use blocking queues to decouple producers from workers.

## CountDownLatch

Allows one or more threads to wait until a count reaches zero.

```java
CountDownLatch latch = new CountDownLatch(3);
latch.countDown();
latch.await();
```

Use for "wait until N tasks finish".

## CyclicBarrier

Allows a group of threads to wait for each other at a common point. It can be reused.

Use for phased parallel algorithms.

## Semaphore

Controls permits.

```java
Semaphore semaphore = new Semaphore(3);
semaphore.acquire();
try {
    // use limited resource
} finally {
    semaphore.release();
}
```

Use for connection pools, rate limits, and bounded concurrent access.

## ThreadLocal

`ThreadLocal<T>` stores one value per thread.

Use cases:

- request context
- correlation ID
- per-thread formatter

Risk: with thread pools, always clear values to avoid leaking context into the next task.

## Deadlock

Deadlock happens when threads wait forever for each other.

Classic conditions:

1. mutual exclusion
2. hold and wait
3. no preemption
4. circular wait

Prevention:

- always acquire locks in the same order
- use timeouts
- keep critical sections small
- avoid calling external code while holding locks

## Java Memory Model And Happens-Before

The Java Memory Model defines when writes by one thread are visible to another.

Common happens-before relationships:

- A thread's actions before `Thread.start()` happen-before actions in the started thread.
- Actions in a thread happen-before another thread successfully returns from `join()` on it.
- Unlocking a monitor happens-before a later lock on the same monitor.
- A write to a volatile variable happens-before a later read of that volatile variable.
- Completing a `Future` happens-before another thread gets its result.

## Virtual Threads

Modern Java includes virtual threads for high-concurrency blocking I/O style code.

```java
try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
    executor.submit(() -> service.callRemoteApi());
}
```

Virtual threads are useful for many blocking tasks. They do not make CPU-heavy work faster. They also do not remove the need for thread-safe shared state.

## LLD Rules Of Thumb

- Use immutable objects when data can be shared across threads.
- Use `ConcurrentHashMap` for shared maps.
- Use `BlockingQueue` for producer-consumer.
- Use `ExecutorService`, not raw thread creation, for repeated async tasks.
- Use `AtomicInteger` or `LongAdder` for counters.
- Use `synchronized` or `Lock` when multiple fields must change atomically together.
- Keep locks private.
- Document thread-safety in class design.

Runnable examples:

- `src/main/java/com/codex/javaconcepts/concurrency/ConcurrencyExamples.java`
- `src/main/java/com/codex/javaconcepts/concurrency/ProducerConsumerBlockingQueue.java`

