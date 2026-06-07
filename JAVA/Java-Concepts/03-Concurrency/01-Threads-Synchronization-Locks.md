# Threads, Synchronization & Locks - Complete Guide

## 1. Thread Basics

### 1.1 Creating Threads - Three Approaches

```java
// ==================== APPROACH 1: Extending Thread ====================
class MyThread extends Thread {
    @Override
    public void run() {
        System.out.println("Thread running: " + Thread.currentThread().getName());
    }
}

// ==================== APPROACH 2: Implementing Runnable ====================
class MyRunnable implements Runnable {
    @Override
    public void run() {
        System.out.println("Runnable running: " + Thread.currentThread().getName());
    }
}

// ==================== APPROACH 3: Implementing Callable ====================
import java.util.concurrent.*;

class MyCallable implements Callable<Integer> {
    @Override
    public Integer call() throws Exception {
        Thread.sleep(1000);
        return 42; // Can return a value
    }
}

// ==================== USAGE ====================
public class ThreadCreationDemo {
    public static void main(String[] args) throws Exception {
        // Method 1: Extend Thread
        MyThread t1 = new MyThread();
        t1.start();
        
        // Method 2: Implement Runnable
        Thread t2 = new Thread(new MyRunnable());
        t2.start();
        
        // Method 2b: Lambda (preferred for simple tasks)
        Thread t3 = new Thread(() -> {
            System.out.println("Lambda thread: " + Thread.currentThread().getName());
        });
        t3.start();
        
        // Method 3: Callable with Future
        ExecutorService executor = Executors.newSingleThreadExecutor();
        Future<Integer> future = executor.submit(new MyCallable());
        System.out.println("Callable result: " + future.get()); // Output: 42
        executor.shutdown();
    }
}
```

### 1.2 Thread vs Runnable vs Callable

| Feature | Thread | Runnable | Callable |
|---------|--------|----------|----------|
| Type | Class (extends) | Interface | Interface |
| Return value | No | No | Yes (via Future) |
| Checked exceptions | Cannot throw | Cannot throw | Can throw |
| Multiple inheritance | No (already extends Thread) | Yes (implements) | Yes (implements) |
| Reusability | Low | High | High |
| Use with ExecutorService | No | Yes | Yes |
| Preferred? | Rarely | Yes | Yes (when result needed) |

### 1.3 Thread Lifecycle (States)

```
        start()
NEW ──────────► RUNNABLE ──────────► TERMINATED
                   │    ▲                  ▲
                   │    │                  │
          sync     │    │ lock acquired    │ run() completes
          lock     │    │                  │ or exception
          needed   │    │                  │
                   ▼    │                  │
               BLOCKED ─┘                  │
                                           │
               wait()/join()               │
  RUNNABLE ──────────────► WAITING ────────┘
                              │      notify()/
                              │      interrupt()
                              │
               sleep(ms)/     │
               wait(ms)       │
  RUNNABLE ──────────────► TIMED_WAITING
                              │
                              │ timeout/notify/interrupt
                              ▼
                           RUNNABLE
```

```java
public class ThreadLifecycleDemo {
    public static void main(String[] args) throws InterruptedException {
        Object lock = new Object();
        
        Thread thread = new Thread(() -> {
            try {
                // RUNNABLE
                synchronized (lock) {
                    // TIMED_WAITING (due to sleep)
                    Thread.sleep(1000);
                    // WAITING (due to wait)
                    lock.wait();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
        
        System.out.println("State after creation: " + thread.getState());    // NEW
        
        thread.start();
        System.out.println("State after start: " + thread.getState());       // RUNNABLE
        
        Thread.sleep(100);
        System.out.println("State during sleep: " + thread.getState());      // TIMED_WAITING
        
        Thread.sleep(1100);
        System.out.println("State during wait: " + thread.getState());       // WAITING
        
        synchronized (lock) {
            lock.notify();
        }
        
        thread.join();
        System.out.println("State after completion: " + thread.getState());  // TERMINATED
    }
}
```

### 1.4 Important Thread Methods

```java
public class ThreadMethodsDemo {
    
    // ==================== start() vs run() ====================
    public static void startVsRun() {
        Thread t = new Thread(() -> {
            System.out.println("Running in: " + Thread.currentThread().getName());
        });
        
        t.run();    // Runs in main thread - NO new thread created!
        t.start();  // Runs in new thread - Correct way!
    }
    
    // ==================== sleep() ====================
    public static void sleepDemo() throws InterruptedException {
        System.out.println("Before sleep: " + System.currentTimeMillis());
        Thread.sleep(2000); // Pauses current thread for 2 seconds
        System.out.println("After sleep: " + System.currentTimeMillis());
        // Note: sleep does NOT release locks
    }
    
    // ==================== join() ====================
    public static void joinDemo() throws InterruptedException {
        Thread t1 = new Thread(() -> {
            try {
                Thread.sleep(2000);
                System.out.println("Thread 1 done");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
        
        Thread t2 = new Thread(() -> {
            System.out.println("Thread 2 done");
        });
        
        t1.start();
        t2.start();
        
        t1.join();  // Main thread waits for t1 to complete
        t2.join();  // Main thread waits for t2 to complete
        
        System.out.println("Both threads completed"); // Guaranteed after both finish
        
        // join with timeout
        Thread longThread = new Thread(() -> {
            try { Thread.sleep(10000); } catch (InterruptedException e) {}
        });
        longThread.start();
        longThread.join(3000); // Wait at most 3 seconds
        System.out.println("Done waiting (thread may still be running)");
    }
    
    // ==================== interrupt() ====================
    public static void interruptDemo() throws InterruptedException {
        Thread worker = new Thread(() -> {
            while (!Thread.currentThread().isInterrupted()) {
                System.out.println("Working...");
                try {
                    Thread.sleep(1000);
                } catch (InterruptedException e) {
                    // sleep() throws InterruptedException and clears interrupt flag
                    System.out.println("Interrupted during sleep!");
                    Thread.currentThread().interrupt(); // Re-set the flag
                    break;
                }
            }
            System.out.println("Thread shutting down gracefully");
        });
        
        worker.start();
        Thread.sleep(3000);
        worker.interrupt(); // Request thread to stop
        worker.join();
    }
    
    // ==================== yield() ====================
    public static void yieldDemo() {
        // Hint to scheduler: "I'm willing to give up my time slice"
        // No guarantee it will actually yield
        Thread t = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("Thread: " + i);
                Thread.yield(); // Suggest scheduling another thread
            }
        });
        t.start();
    }
    
    // ==================== setDaemon() ====================
    public static void daemonDemo() {
        Thread daemon = new Thread(() -> {
            while (true) {
                System.out.println("Daemon thread running...");
                try { Thread.sleep(500); } catch (InterruptedException e) { break; }
            }
        });
        
        daemon.setDaemon(true); // MUST be set before start()
        daemon.start();
        
        // When all non-daemon threads finish, JVM exits
        // Daemon threads are killed automatically
        // Use for: garbage collection, cache cleanup, monitoring
        
        try { Thread.sleep(2000); } catch (InterruptedException e) {}
        System.out.println("Main thread ending - daemon will be killed");
    }
    
    // ==================== setPriority() ====================
    public static void priorityDemo() {
        Thread low = new Thread(() -> {
            for (int i = 0; i < 5; i++) System.out.println("LOW: " + i);
        });
        Thread high = new Thread(() -> {
            for (int i = 0; i < 5; i++) System.out.println("HIGH: " + i);
        });
        
        low.setPriority(Thread.MIN_PRIORITY);   // 1
        high.setPriority(Thread.MAX_PRIORITY);  // 10
        // Thread.NORM_PRIORITY = 5 (default)
        
        // NOTE: Priority is only a hint to the OS scheduler
        // No guarantee high-priority thread runs first
        low.start();
        high.start();
    }
}
```

---

## 2. Synchronization

### 2.1 Race Condition (The Problem)

```java
public class RaceConditionDemo {
    private int counter = 0;
    
    public void increment() {
        counter++; // NOT atomic! Read → Modify → Write
    }
    
    public static void main(String[] args) throws InterruptedException {
        RaceConditionDemo demo = new RaceConditionDemo();
        
        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.increment();
        });
        
        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.increment();
        });
        
        t1.start();
        t2.start();
        t1.join();
        t2.join();
        
        // Expected: 200000
        // Actual: Something less (e.g., 167834) - RACE CONDITION!
        System.out.println("Counter: " + demo.counter);
    }
}

/*
WHY? counter++ is actually THREE operations:
1. READ counter value (e.g., 5)
2. INCREMENT in register (5 → 6)
3. WRITE back to counter (counter = 6)

If T1 reads 5, then T2 reads 5 (before T1 writes),
both write 6. One increment is LOST.
*/
```

### 2.2 synchronized Keyword

```java
public class SynchronizedDemo {
    private int counter = 0;
    
    // ==================== Method-level synchronization ====================
    // Lock: 'this' object (instance lock)
    public synchronized void incrementSync() {
        counter++;
    }
    
    // ==================== Block-level synchronization ====================
    // More granular - lock only critical section
    private final Object lock = new Object();
    
    public void incrementBlock() {
        // Non-critical code can run concurrently
        System.out.println("Before critical section");
        
        synchronized (lock) { // Only this block is serialized
            counter++;
        }
        
        // More non-critical code
        System.out.println("After critical section");
    }
    
    // ==================== Static synchronization (class-level lock) ====================
    private static int staticCounter = 0;
    
    // Lock: SynchronizedDemo.class object
    public static synchronized void staticIncrement() {
        staticCounter++;
    }
    
    // Equivalent to:
    public static void staticIncrementBlock() {
        synchronized (SynchronizedDemo.class) {
            staticCounter++;
        }
    }
    
    public static void main(String[] args) throws InterruptedException {
        SynchronizedDemo demo = new SynchronizedDemo();
        
        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.incrementSync();
        });
        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.incrementSync();
        });
        
        t1.start(); t2.start();
        t1.join(); t2.join();
        
        System.out.println("Counter: " + demo.counter); // Always 200000
    }
}
```

### 2.3 Object-Level Lock vs Class-Level Lock

```java
public class LockLevelsDemo {
    
    // ==================== Object-Level Lock ====================
    // Each instance has its own lock
    // Two different instances can execute concurrently
    
    public synchronized void instanceMethod() {
        // Acquires lock on 'this'
        System.out.println(Thread.currentThread().getName() + " in instanceMethod");
        try { Thread.sleep(2000); } catch (InterruptedException e) {}
    }
    
    // ==================== Class-Level Lock ====================
    // Only ONE thread across ALL instances can enter
    
    public static synchronized void classMethod() {
        // Acquires lock on LockLevelsDemo.class
        System.out.println(Thread.currentThread().getName() + " in classMethod");
        try { Thread.sleep(2000); } catch (InterruptedException e) {}
    }
    
    public static void main(String[] args) {
        LockLevelsDemo obj1 = new LockLevelsDemo();
        LockLevelsDemo obj2 = new LockLevelsDemo();
        
        // Object-level: These two CAN run in parallel (different locks!)
        new Thread(() -> obj1.instanceMethod(), "T1-obj1").start();
        new Thread(() -> obj2.instanceMethod(), "T2-obj2").start();
        
        // Object-level: These two CANNOT run in parallel (same lock!)
        new Thread(() -> obj1.instanceMethod(), "T3-obj1").start();
        new Thread(() -> obj1.instanceMethod(), "T4-obj1").start();
        
        // Class-level: These CANNOT run in parallel regardless of instance
        new Thread(LockLevelsDemo::classMethod, "T5-class").start();
        new Thread(LockLevelsDemo::classMethod, "T6-class").start();
    }
}
```

### 2.4 Reentrant Locking

```java
public class ReentrantLockingDemo {
    
    // synchronized is REENTRANT - same thread can acquire the same lock multiple times
    
    public synchronized void methodA() {
        System.out.println("In methodA");
        methodB(); // Can call another synchronized method - same thread holds lock
    }
    
    public synchronized void methodB() {
        System.out.println("In methodB");
        methodC(); // Can go deeper - lock count increments
    }
    
    public synchronized void methodC() {
        System.out.println("In methodC");
        // Lock is released only when ALL nested synchronized blocks exit
    }
    
    public static void main(String[] args) {
        ReentrantLockingDemo demo = new ReentrantLockingDemo();
        demo.methodA();
        // Output:
        // In methodA
        // In methodB
        // In methodC
        // No deadlock! Same thread re-enters its own locks
    }
}
```

### 2.5 volatile Keyword

```java
public class VolatileDemo {
    
    // WITHOUT volatile - thread may never see the update (cached in CPU register)
    // private boolean running = true;
    
    // WITH volatile - guarantees visibility across threads
    private volatile boolean running = true;
    
    public void worker() {
        int count = 0;
        while (running) { // Without volatile, this might run forever
            count++;
        }
        System.out.println("Stopped after count: " + count);
    }
    
    public void stop() {
        running = false; // This write is immediately visible to all threads
    }
    
    public static void main(String[] args) throws InterruptedException {
        VolatileDemo demo = new VolatileDemo();
        
        Thread worker = new Thread(demo::worker);
        worker.start();
        
        Thread.sleep(1000);
        demo.stop(); // Worker thread WILL see this change due to volatile
        worker.join();
    }
}

// ==================== volatile does NOT provide atomicity ====================
class VolatileNotAtomic {
    private volatile int counter = 0; // Still NOT thread-safe for counter++!
    
    public void increment() {
        counter++; // Still read-modify-write, volatile doesn't help
    }
    
    // volatile guarantees:
    // 1. VISIBILITY: writes are immediately visible to other threads
    // 2. ORDERING: prevents instruction reordering (memory barrier)
    
    // volatile does NOT guarantee:
    // 1. ATOMICITY: compound operations (like ++) are still unsafe
    
    // Use volatile for:
    // - Flags (boolean running = true)
    // - One writer, multiple readers
    // - Publishing immutable objects
    
    // Do NOT use volatile for:
    // - counter++ (use AtomicInteger)
    // - check-then-act patterns (use synchronized)
}
```

### 2.6 Happens-Before Relationship

```java
/*
HAPPENS-BEFORE is a guarantee that memory writes by one statement
are visible to another specific statement.

Key happens-before rules:

1. PROGRAM ORDER RULE:
   Each action in a thread happens-before every subsequent action in that thread.
   
2. MONITOR LOCK RULE:
   An unlock on a monitor happens-before every subsequent lock on that same monitor.
   synchronized(lock) { x = 1; } // WRITE
   synchronized(lock) { y = x; } // READ sees x = 1

3. VOLATILE VARIABLE RULE:
   A write to a volatile field happens-before every subsequent read of that field.
   volatile int x;
   x = 1;           // Thread A writes
   int y = x;       // Thread B reads - guaranteed to see 1

4. THREAD START RULE:
   A call to Thread.start() happens-before any action in the started thread.
   x = 5;
   thread.start();  // thread.run() sees x = 5

5. THREAD TERMINATION RULE:
   Any action in a thread happens-before another thread detects termination (join/isAlive).
   
6. TRANSITIVITY:
   If A happens-before B, and B happens-before C, then A happens-before C.
*/

public class HappensBeforeDemo {
    private int x = 0;
    private volatile boolean ready = false; // volatile acts as memory barrier
    
    public void writer() {
        x = 42;          // (1) Non-volatile write
        ready = true;    // (2) Volatile write - creates happens-before edge
    }
    
    public void reader() {
        if (ready) {           // (3) Volatile read
            System.out.println(x); // (4) Guaranteed to see 42!
            // Because (1) happens-before (2) [program order]
            // And (2) happens-before (3) [volatile rule]
            // So (1) happens-before (4) [transitivity]
        }
    }
}
```

---

## 3. Locks (java.util.concurrent.locks)

### 3.1 ReentrantLock

```java
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.TimeUnit;

public class ReentrantLockDemo {
    private final ReentrantLock lock = new ReentrantLock();
    // ReentrantLock(true) = fair lock (longest-waiting thread gets lock)
    // ReentrantLock(false) = unfair (default, better throughput)
    
    private int counter = 0;
    
    // ==================== Basic lock/unlock ====================
    public void increment() {
        lock.lock(); // Acquire lock (blocks if unavailable)
        try {
            counter++;
        } finally {
            lock.unlock(); // ALWAYS unlock in finally!
        }
    }
    
    // ==================== tryLock (non-blocking) ====================
    public boolean tryIncrement() {
        if (lock.tryLock()) { // Returns immediately with true/false
            try {
                counter++;
                return true;
            } finally {
                lock.unlock();
            }
        } else {
            System.out.println("Could not acquire lock, doing other work");
            return false;
        }
    }
    
    // ==================== tryLock with timeout ====================
    public boolean tryIncrementWithTimeout() throws InterruptedException {
        if (lock.tryLock(2, TimeUnit.SECONDS)) { // Wait up to 2 seconds
            try {
                counter++;
                return true;
            } finally {
                lock.unlock();
            }
        } else {
            System.out.println("Timeout waiting for lock");
            return false;
        }
    }
    
    // ==================== lockInterruptibly ====================
    public void interruptibleIncrement() throws InterruptedException {
        lock.lockInterruptibly(); // Can be interrupted while waiting
        try {
            counter++;
        } finally {
            lock.unlock();
        }
    }
    
    // ==================== Lock info methods ====================
    public void lockInfo() {
        System.out.println("Is locked: " + lock.isLocked());
        System.out.println("Is held by current thread: " + lock.isHeldByCurrentThread());
        System.out.println("Hold count: " + lock.getHoldCount());
        System.out.println("Has queued threads: " + lock.hasQueuedThreads());
        System.out.println("Queue length: " + lock.getQueueLength());
    }
    
    public static void main(String[] args) throws InterruptedException {
        ReentrantLockDemo demo = new ReentrantLockDemo();
        
        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.increment();
        });
        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 100000; i++) demo.increment();
        });
        
        t1.start(); t2.start();
        t1.join(); t2.join();
        
        System.out.println("Counter: " + demo.counter); // Always 200000
    }
}
```

### 3.2 ReadWriteLock

```java
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.*;

public class ReadWriteLockDemo {
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
    private final Map<String, String> cache = new HashMap<>();
    
    /*
    Rules:
    - Multiple threads can hold READ lock simultaneously
    - Only ONE thread can hold WRITE lock (exclusive)
    - If write lock is held, no read locks can be acquired
    - If any read lock is held, write lock cannot be acquired
    
    Read-Read:   ALLOWED (concurrent)
    Read-Write:  BLOCKED
    Write-Write: BLOCKED
    */
    
    // Multiple threads can read simultaneously
    public String get(String key) {
        rwLock.readLock().lock();
        try {
            System.out.println(Thread.currentThread().getName() + " reading");
            Thread.sleep(100); // Simulate slow read
            return cache.get(key);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null;
        } finally {
            rwLock.readLock().unlock();
        }
    }
    
    // Only one thread can write at a time (exclusive)
    public void put(String key, String value) {
        rwLock.writeLock().lock();
        try {
            System.out.println(Thread.currentThread().getName() + " writing");
            Thread.sleep(500); // Simulate slow write
            cache.put(key, value);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            rwLock.writeLock().unlock();
        }
    }
    
    public static void main(String[] args) throws InterruptedException {
        ReadWriteLockDemo demo = new ReadWriteLockDemo();
        demo.put("key1", "value1"); // Pre-populate
        
        // Multiple readers run in PARALLEL
        for (int i = 0; i < 5; i++) {
            new Thread(() -> {
                System.out.println("Read: " + demo.get("key1"));
            }, "Reader-" + i).start();
        }
        
        // Writer must wait for all readers to finish
        new Thread(() -> demo.put("key1", "updated"), "Writer-1").start();
        
        Thread.sleep(3000);
    }
}
```

### 3.3 StampedLock (Java 8)

```java
import java.util.concurrent.locks.StampedLock;

public class StampedLockDemo {
    private final StampedLock sl = new StampedLock();
    private double x, y;
    
    /*
    StampedLock has THREE modes:
    1. Write Lock (exclusive) - like ReentrantWriteLock
    2. Read Lock (shared) - like ReentrantReadLock  
    3. Optimistic Read - NO lock acquired! Just validates later
    
    Optimistic reads are for read-heavy workloads where contention is rare.
    Much better performance than ReadWriteLock when reads >> writes.
    
    NOTE: StampedLock is NOT reentrant! Do not call from same thread.
    */
    
    // Exclusive write lock
    public void move(double deltaX, double deltaY) {
        long stamp = sl.writeLock();
        try {
            x += deltaX;
            y += deltaY;
        } finally {
            sl.unlockWrite(stamp);
        }
    }
    
    // Optimistic read - BEST PERFORMANCE for reads
    public double distanceFromOrigin() {
        long stamp = sl.tryOptimisticRead(); // Non-blocking! Returns stamp, not lock
        double currentX = x;
        double currentY = y;
        
        if (!sl.validate(stamp)) {
            // A write occurred since we got the stamp - fall back to read lock
            stamp = sl.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                sl.unlockRead(stamp);
            }
        }
        
        return Math.sqrt(currentX * currentX + currentY * currentY);
    }
    
    // Regular read lock (for longer critical sections)
    public double getX() {
        long stamp = sl.readLock();
        try {
            return x;
        } finally {
            sl.unlockRead(stamp);
        }
    }
    
    // Lock upgrade: read → write
    public void moveIfAtOrigin(double newX, double newY) {
        long stamp = sl.readLock();
        try {
            while (x == 0.0 && y == 0.0) {
                long writeStamp = sl.tryConvertToWriteLock(stamp);
                if (writeStamp != 0L) {
                    // Successfully upgraded
                    stamp = writeStamp;
                    x = newX;
                    y = newY;
                    break;
                } else {
                    // Upgrade failed - release read, acquire write
                    sl.unlockRead(stamp);
                    stamp = sl.writeLock();
                }
            }
        } finally {
            sl.unlock(stamp); // Works with any lock mode
        }
    }
    
    public static void main(String[] args) {
        StampedLockDemo point = new StampedLockDemo();
        
        // Writers
        new Thread(() -> point.move(3.0, 4.0)).start();
        
        // Readers (using optimistic read - very fast)
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                System.out.println("Distance: " + point.distanceFromOrigin());
            }).start();
        }
    }
}
```

### 3.4 Condition (await/signal)

```java
import java.util.concurrent.locks.*;
import java.util.LinkedList;
import java.util.Queue;

public class ConditionDemo {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();  // wait when full
    private final Condition notEmpty = lock.newCondition(); // wait when empty
    
    private final Queue<Integer> queue = new LinkedList<>();
    private final int CAPACITY = 5;
    
    /*
    Condition replaces Object's wait/notify mechanism:
    
    Object method    →  Condition equivalent
    ─────────────────────────────────────────
    wait()           →  await()
    wait(timeout)    →  await(time, unit)
    notify()         →  signal()
    notifyAll()      →  signalAll()
    
    Advantage: Multiple conditions per lock (e.g., notFull, notEmpty)
    With synchronized: only ONE wait set per object
    */
    
    public void produce(int item) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == CAPACITY) {
                System.out.println("Queue full, producer waiting...");
                notFull.await(); // Release lock and wait
            }
            queue.offer(item);
            System.out.println("Produced: " + item + " | Size: " + queue.size());
            notEmpty.signal(); // Wake up ONE consumer
        } finally {
            lock.unlock();
        }
    }
    
    public int consume() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) {
                System.out.println("Queue empty, consumer waiting...");
                notEmpty.await(); // Release lock and wait
            }
            int item = queue.poll();
            System.out.println("Consumed: " + item + " | Size: " + queue.size());
            notFull.signal(); // Wake up ONE producer
            return item;
        } finally {
            lock.unlock();
        }
    }
    
    public static void main(String[] args) {
        ConditionDemo buffer = new ConditionDemo();
        
        Thread producer = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                try { buffer.produce(i); } catch (InterruptedException e) { break; }
            }
        });
        
        Thread consumer = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                try { buffer.consume(); } catch (InterruptedException e) { break; }
            }
        });
        
        producer.start();
        consumer.start();
    }
}
```

### 3.5 Lock vs synchronized Comparison

| Feature | synchronized | ReentrantLock |
|---------|-------------|---------------|
| Syntax | Simple block/method | Explicit lock/unlock |
| Auto-release | Yes (on block exit) | No (must use finally) |
| Fairness | Not configurable | Yes (fair=true) |
| tryLock | Not possible | Yes |
| Interruptible wait | Not possible | lockInterruptibly() |
| Timeout | Not possible | tryLock(timeout) |
| Multiple conditions | No (one wait set) | Yes (multiple Conditions) |
| Performance | Similar (optimized in modern JVMs) | Similar |
| Reentrant | Yes | Yes |
| Lock info | No | isLocked(), getHoldCount() |
| Read/Write separation | No | ReadWriteLock |
| When to use | Simple synchronization | Need advanced features |

---

## 4. Classic Concurrency Problems

### 4.1 Producer-Consumer with wait/notify

```java
import java.util.LinkedList;
import java.util.Queue;

public class ProducerConsumerWaitNotify {
    private final Queue<Integer> queue = new LinkedList<>();
    private final int CAPACITY = 5;
    private final Object lock = new Object();
    
    public void produce() throws InterruptedException {
        int value = 0;
        while (true) {
            synchronized (lock) {
                // MUST use while (not if) - spurious wakeups!
                while (queue.size() == CAPACITY) {
                    System.out.println("Queue FULL - Producer waiting");
                    lock.wait(); // Releases lock, waits for notification
                }
                
                queue.offer(value);
                System.out.println("Produced: " + value + " | Queue size: " + queue.size());
                value++;
                
                lock.notifyAll(); // Wake up consumers
            }
            Thread.sleep(100); // Simulate work
        }
    }
    
    public void consume() throws InterruptedException {
        while (true) {
            synchronized (lock) {
                while (queue.isEmpty()) {
                    System.out.println("Queue EMPTY - Consumer waiting");
                    lock.wait();
                }
                
                int item = queue.poll();
                System.out.println("Consumed: " + item + " | Queue size: " + queue.size());
                
                lock.notifyAll(); // Wake up producers
            }
            Thread.sleep(200); // Simulate processing
        }
    }
    
    public static void main(String[] args) {
        ProducerConsumerWaitNotify pc = new ProducerConsumerWaitNotify();
        
        Thread producer = new Thread(() -> {
            try { pc.produce(); } catch (InterruptedException e) {}
        });
        
        Thread consumer = new Thread(() -> {
            try { pc.consume(); } catch (InterruptedException e) {}
        });
        
        producer.start();
        consumer.start();
    }
}
```

### 4.2 Producer-Consumer with BlockingQueue (Preferred)

```java
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ArrayBlockingQueue;

public class ProducerConsumerBlockingQueue {
    
    // BlockingQueue handles ALL synchronization internally!
    private final BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(5);
    
    public void produce() throws InterruptedException {
        int value = 0;
        while (true) {
            queue.put(value); // BLOCKS if queue is full (no manual wait needed!)
            System.out.println("Produced: " + value);
            value++;
            Thread.sleep(100);
        }
    }
    
    public void consume() throws InterruptedException {
        while (true) {
            int item = queue.take(); // BLOCKS if queue is empty
            System.out.println("Consumed: " + item);
            Thread.sleep(200);
        }
    }
    
    public static void main(String[] args) {
        ProducerConsumerBlockingQueue pc = new ProducerConsumerBlockingQueue();
        
        // Multiple producers and consumers
        new Thread(() -> { try { pc.produce(); } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { pc.produce(); } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { pc.consume(); } catch (InterruptedException e) {} }).start();
    }
}

/*
BlockingQueue Methods Summary:
─────────────────────────────────────────────────────
           | Throws     | Returns   | Blocks  | Times out
───────────|───────────|──────────|─────────|──────────
Insert     | add(e)     | offer(e)  | put(e)  | offer(e, timeout)
Remove     | remove()   | poll()    | take()  | poll(timeout)
Examine    | element()  | peek()    | N/A     | N/A

Implementations:
- ArrayBlockingQueue: bounded, fixed capacity
- LinkedBlockingQueue: optionally bounded (default Integer.MAX_VALUE)
- PriorityBlockingQueue: unbounded, priority-ordered
- SynchronousQueue: zero capacity! Each put waits for a take
- DelayQueue: elements available after a delay
*/
```

### 4.3 Reader-Writer Problem

```java
import java.util.concurrent.locks.*;

public class ReaderWriterProblem {
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
    private String sharedData = "Initial";
    private int readerCount = 0;
    
    public void read(String readerName) {
        rwLock.readLock().lock();
        try {
            readerCount++;
            System.out.println(readerName + " is reading: " + sharedData 
                             + " [Active readers: " + readerCount + "]");
            Thread.sleep(1000); // Simulate reading
            readerCount--;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            rwLock.readLock().unlock();
        }
    }
    
    public void write(String writerName, String data) {
        rwLock.writeLock().lock();
        try {
            System.out.println(writerName + " is writing: " + data);
            Thread.sleep(2000); // Simulate writing
            sharedData = data;
            System.out.println(writerName + " finished writing");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            rwLock.writeLock().unlock();
        }
    }
    
    public static void main(String[] args) {
        ReaderWriterProblem rw = new ReaderWriterProblem();
        
        // Multiple readers can read simultaneously
        for (int i = 1; i <= 5; i++) {
            final int id = i;
            new Thread(() -> rw.read("Reader-" + id)).start();
        }
        
        // Writer must wait for all readers
        new Thread(() -> rw.write("Writer-1", "Updated Data")).start();
        
        // These readers must wait for writer
        for (int i = 6; i <= 8; i++) {
            final int id = i;
            new Thread(() -> rw.read("Reader-" + id)).start();
        }
    }
}
```

### 4.4 Dining Philosophers

```java
import java.util.concurrent.locks.ReentrantLock;

public class DiningPhilosophers {
    private static final int NUM_PHILOSOPHERS = 5;
    private final ReentrantLock[] forks = new ReentrantLock[NUM_PHILOSOPHERS];
    
    public DiningPhilosophers() {
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            forks[i] = new ReentrantLock();
        }
    }
    
    /*
    DEADLOCK PREVENTION STRATEGY: Resource Ordering
    
    Instead of each philosopher picking up left fork first,
    we impose an ordering: always pick up the lower-numbered fork first.
    
    This breaks the circular wait condition.
    */
    
    public void startEating(int philosopherId) {
        int leftFork = philosopherId;
        int rightFork = (philosopherId + 1) % NUM_PHILOSOPHERS;
        
        // Always acquire lower-numbered fork first (prevents deadlock)
        int firstFork = Math.min(leftFork, rightFork);
        int secondFork = Math.max(leftFork, rightFork);
        
        forks[firstFork].lock();
        try {
            forks[secondFork].lock();
            try {
                eat(philosopherId);
            } finally {
                forks[secondFork].unlock();
            }
        } finally {
            forks[firstFork].unlock();
        }
    }
    
    private void eat(int id) {
        System.out.println("Philosopher " + id + " is EATING");
        try { Thread.sleep(1000); } catch (InterruptedException e) {}
        System.out.println("Philosopher " + id + " finished eating");
    }
    
    private void think(int id) {
        System.out.println("Philosopher " + id + " is THINKING");
        try { Thread.sleep((long)(Math.random() * 2000)); } catch (InterruptedException e) {}
    }
    
    public static void main(String[] args) {
        DiningPhilosophers dp = new DiningPhilosophers();
        
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            final int id = i;
            new Thread(() -> {
                while (true) {
                    dp.think(id);
                    dp.startEating(id);
                }
            }, "Philosopher-" + i).start();
        }
    }
}

/*
DEADLOCK PREVENTION STRATEGIES:
1. Resource Ordering (used above) - always acquire locks in same order
2. tryLock with timeout - give up if can't acquire both
3. Single global lock - simple but kills parallelism
4. Chandy/Misra solution - message passing with dirty/clean forks
*/
```

### 4.5 Print Numbers Alternately Using 2 Threads

```java
// ==================== Solution 1: Using wait/notify ====================
public class PrintAlternateWaitNotify {
    private final Object lock = new Object();
    private boolean isOddTurn = true;
    private final int MAX = 20;
    
    public void printOdd() throws InterruptedException {
        synchronized (lock) {
            for (int i = 1; i <= MAX; i += 2) {
                while (!isOddTurn) {
                    lock.wait();
                }
                System.out.println("Odd Thread: " + i);
                isOddTurn = false;
                lock.notify();
            }
        }
    }
    
    public void printEven() throws InterruptedException {
        synchronized (lock) {
            for (int i = 2; i <= MAX; i += 2) {
                while (isOddTurn) {
                    lock.wait();
                }
                System.out.println("Even Thread: " + i);
                isOddTurn = true;
                lock.notify();
            }
        }
    }
    
    public static void main(String[] args) {
        PrintAlternateWaitNotify printer = new PrintAlternateWaitNotify();
        
        Thread t1 = new Thread(() -> {
            try { printer.printOdd(); } catch (InterruptedException e) {}
        });
        Thread t2 = new Thread(() -> {
            try { printer.printEven(); } catch (InterruptedException e) {}
        });
        
        t1.start();
        t2.start();
    }
}
// Output:
// Odd Thread: 1
// Even Thread: 2
// Odd Thread: 3
// Even Thread: 4
// ... up to 20

// ==================== Solution 2: Using Semaphore ====================
import java.util.concurrent.Semaphore;

class PrintAlternateSemaphore {
    private final Semaphore oddSem = new Semaphore(1);  // Start with odd
    private final Semaphore evenSem = new Semaphore(0); // Even waits first
    private final int MAX = 20;
    
    public void printOdd() throws InterruptedException {
        for (int i = 1; i <= MAX; i += 2) {
            oddSem.acquire();  // Wait for permission
            System.out.println("Odd: " + i);
            evenSem.release(); // Give permission to even
        }
    }
    
    public void printEven() throws InterruptedException {
        for (int i = 2; i <= MAX; i += 2) {
            evenSem.acquire(); // Wait for permission
            System.out.println("Even: " + i);
            oddSem.release();  // Give permission to odd
        }
    }
    
    public static void main(String[] args) {
        PrintAlternateSemaphore printer = new PrintAlternateSemaphore();
        new Thread(() -> { try { printer.printOdd(); } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { printer.printEven(); } catch (InterruptedException e) {} }).start();
    }
}
```

### 4.6 Deadlock Example and Prevention

```java
public class DeadlockDemo {
    private final Object lockA = new Object();
    private final Object lockB = new Object();
    
    // ==================== DEADLOCK SCENARIO ====================
    public void method1() {
        synchronized (lockA) {         // Thread-1 holds lockA
            System.out.println("Thread-1: Holding lockA");
            try { Thread.sleep(100); } catch (InterruptedException e) {}
            
            synchronized (lockB) {     // Thread-1 waits for lockB (held by Thread-2)
                System.out.println("Thread-1: Holding lockA and lockB");
            }
        }
    }
    
    public void method2() {
        synchronized (lockB) {         // Thread-2 holds lockB
            System.out.println("Thread-2: Holding lockB");
            try { Thread.sleep(100); } catch (InterruptedException e) {}
            
            synchronized (lockA) {     // Thread-2 waits for lockA (held by Thread-1)
                System.out.println("Thread-2: Holding lockB and lockA");
            }
        }
    }
    
    // DEADLOCK! Thread-1 waits for lockB, Thread-2 waits for lockA - circular dependency
    
    public static void main(String[] args) {
        DeadlockDemo demo = new DeadlockDemo();
        new Thread(demo::method1, "Thread-1").start();
        new Thread(demo::method2, "Thread-2").start();
    }
}

// ==================== DEADLOCK PREVENTION ====================
class DeadlockPrevention {
    private final Object lockA = new Object();
    private final Object lockB = new Object();
    
    // STRATEGY 1: Lock Ordering (always acquire locks in same order)
    public void method1Fixed() {
        synchronized (lockA) {         // Always lockA first
            synchronized (lockB) {     // Then lockB
                System.out.println("Method1 executing");
            }
        }
    }
    
    public void method2Fixed() {
        synchronized (lockA) {         // Always lockA first (same order!)
            synchronized (lockB) {     // Then lockB
                System.out.println("Method2 executing");
            }
        }
    }
    
    // STRATEGY 2: tryLock with timeout
    private final java.util.concurrent.locks.ReentrantLock lock1 = 
        new java.util.concurrent.locks.ReentrantLock();
    private final java.util.concurrent.locks.ReentrantLock lock2 = 
        new java.util.concurrent.locks.ReentrantLock();
    
    public void safeMethod() {
        boolean acquired = false;
        while (!acquired) {
            try {
                if (lock1.tryLock(100, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                    try {
                        if (lock2.tryLock(100, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                            try {
                                // Critical section
                                System.out.println("Both locks acquired safely");
                                acquired = true;
                            } finally {
                                lock2.unlock();
                            }
                        }
                    } finally {
                        lock1.unlock();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            
            if (!acquired) {
                // Back off and retry
                try { Thread.sleep((long)(Math.random() * 100)); } 
                catch (InterruptedException e) { break; }
            }
        }
    }
}

/*
FOUR CONDITIONS FOR DEADLOCK (ALL must be true):
1. Mutual Exclusion: Resource can be held by only one thread
2. Hold and Wait: Thread holds resource while waiting for another
3. No Preemption: Resources cannot be forcibly taken
4. Circular Wait: T1 → T2 → T3 → T1

PREVENTION STRATEGIES:
1. Lock ordering (break circular wait)
2. Lock timeout with tryLock (break hold & wait)
3. Single lock (break mutual exclusion / simplify)
4. Avoid nested locks when possible
5. Use higher-level concurrency utilities (java.util.concurrent)

DETECTION:
- jstack <pid>: shows thread dump with deadlock info
- ThreadMXBean.findDeadlockedThreads()
- VisualVM, JConsole monitoring tools
*/
```

---

## 5. Thread Safety Patterns

### 5.1 Immutable Objects

```java
// Immutable objects are ALWAYS thread-safe (no synchronization needed)
public final class ImmutablePerson {
    private final String name;
    private final int age;
    private final List<String> hobbies; // Mutable field - special handling needed
    
    public ImmutablePerson(String name, int age, List<String> hobbies) {
        this.name = name;
        this.age = age;
        // DEFENSIVE COPY - don't let external code modify our list
        this.hobbies = Collections.unmodifiableList(new ArrayList<>(hobbies));
    }
    
    public String getName() { return name; }
    public int getAge() { return age; }
    public List<String> getHobbies() { return hobbies; } // Already unmodifiable
    
    // No setters! To "modify", create a new instance:
    public ImmutablePerson withAge(int newAge) {
        return new ImmutablePerson(this.name, newAge, this.hobbies);
    }
}

/*
Rules for immutability:
1. Class is final (cannot be subclassed)
2. All fields are private and final
3. No setters
4. Defensive copies of mutable fields (in constructor AND getters)
5. Don't leak 'this' during construction

Thread safety: Multiple threads can safely read without synchronization.
Examples in JDK: String, Integer, LocalDate, BigDecimal
*/
```

### 5.2 ThreadLocal

```java
import java.text.SimpleDateFormat;
import java.util.Date;

public class ThreadLocalDemo {
    
    // Each thread gets its own copy - no sharing, no synchronization needed
    private static final ThreadLocal<SimpleDateFormat> dateFormatter =
        ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd HH:mm:ss"));
    
    // Common use case: User context per request in web apps
    private static final ThreadLocal<String> userContext = new ThreadLocal<>();
    
    // Thread-local counter
    private static final ThreadLocal<Integer> requestCount = 
        ThreadLocal.withInitial(() -> 0);
    
    public static void main(String[] args) throws InterruptedException {
        // Example 1: Date formatting (SimpleDateFormat is NOT thread-safe)
        Runnable dateTask = () -> {
            String formatted = dateFormatter.get().format(new Date());
            System.out.println(Thread.currentThread().getName() + ": " + formatted);
        };
        
        Thread t1 = new Thread(dateTask, "Thread-1");
        Thread t2 = new Thread(dateTask, "Thread-2");
        t1.start(); t2.start();
        t1.join(); t2.join();
        
        // Example 2: User context
        Thread userThread1 = new Thread(() -> {
            userContext.set("Alice");
            processRequest();
            userContext.remove(); // IMPORTANT: Prevent memory leaks!
        });
        
        Thread userThread2 = new Thread(() -> {
            userContext.set("Bob");
            processRequest();
            userContext.remove();
        });
        
        userThread1.start(); userThread2.start();
    }
    
    private static void processRequest() {
        System.out.println("Processing for user: " + userContext.get());
        // Each thread sees its own value - no interference!
    }
}

/*
ThreadLocal pitfalls:
1. MEMORY LEAKS with thread pools: Thread survives, ThreadLocal value lingers
   ALWAYS call remove() in finally block, especially with thread pools
   
2. InheritableThreadLocal: Child threads inherit parent's values
   private static final InheritableThreadLocal<String> ctx = new InheritableThreadLocal<>();

3. Common use cases:
   - Database connections per thread
   - User session/context in web frameworks
   - Transaction context
   - Non-thread-safe objects (SimpleDateFormat, Random)
*/
```

### 5.3 Confinement

```java
public class ConfinementPatterns {
    
    // ==================== STACK CONFINEMENT ====================
    // Local variables are inherently thread-safe (on thread's stack)
    public long calculateSum(int[] numbers) {
        long sum = 0;                    // Stack-confined, private to this invocation
        List<Integer> temp = new ArrayList<>(); // Also stack-confined
        
        for (int n : numbers) {
            temp.add(n);
            sum += n;
        }
        
        return sum; // No synchronization needed - sum is never shared
    }
    
    // ==================== THREAD-LOCAL CONFINEMENT ====================
    // Object exists only within one thread's ThreadLocal
    private static final ThreadLocal<Connection> connectionHolder = 
        ThreadLocal.withInitial(() -> createConnection());
    
    public void doWork() {
        Connection conn = connectionHolder.get(); // Only THIS thread's connection
        // Use conn safely - no other thread has access
    }
    
    private static Connection createConnection() {
        // Factory method for creating connections
        return null; // placeholder
    }
    
    // ==================== OBJECT CONFINEMENT (Ad-hoc) ====================
    // Confine mutable state within a synchronized wrapper
    public class ConfinedCollection {
        private final List<String> items = new ArrayList<>(); // Mutable, not thread-safe
        
        // All access goes through synchronized methods
        public synchronized void add(String item) {
            items.add(item);
        }
        
        public synchronized String get(int index) {
            return items.get(index);
        }
        
        public synchronized int size() {
            return items.size();
        }
        
        // NEVER expose the raw list:
        // public List<String> getItems() { return items; } // WRONG! Breaks confinement!
        
        public synchronized List<String> getItems() {
            return new ArrayList<>(items); // Return defensive copy
        }
    }
    
    // Placeholder interface
    interface Connection { }
}

/*
SUMMARY OF THREAD SAFETY STRATEGIES:

1. IMMUTABILITY: Make objects immutable (final fields, no setters)
   → No synchronization needed ever

2. THREAD CONFINEMENT: Don't share the object between threads
   → Stack confinement: local variables
   → ThreadLocal: per-thread instances
   
3. SYNCHRONIZATION: Share the object but coordinate access
   → synchronized, Lock, AtomicXxx
   
4. CONCURRENT DATA STRUCTURES: Use thread-safe collections
   → ConcurrentHashMap, CopyOnWriteArrayList, BlockingQueue
   
Preference order: 1 > 2 > 4 > 3
(Immutability is simplest, explicit synchronization is most error-prone)
*/
```

---

## Quick Reference: Thread Methods Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────────────┐
│ METHOD              │ RELEASES LOCK? │ STATIC? │ NOTES                  │
├─────────────────────┼────────────────┼─────────┼────────────────────────┤
│ start()             │ N/A            │ No      │ Creates new thread     │
│ run()               │ N/A            │ No      │ Called in same thread   │
│ sleep(ms)           │ NO             │ Yes     │ Thread.sleep()         │
│ join()              │ YES (own lock) │ No      │ Wait for thread to die │
│ wait()              │ YES            │ No      │ Must be in sync block  │
│ notify()/notifyAll()│ NO             │ No      │ Must be in sync block  │
│ yield()             │ NO             │ Yes     │ Hint, no guarantee     │
│ interrupt()         │ NO             │ No      │ Sets interrupt flag    │
│ setDaemon(true)     │ N/A            │ No      │ Before start() only    │
│ setPriority(n)      │ N/A            │ No      │ 1-10, hint only        │
└─────────────────────────────────────────────────────────────────────────┘

KEY DIFFERENCES:
- sleep vs wait: sleep doesn't release lock, wait does
- notify vs notifyAll: notify wakes ONE thread, notifyAll wakes ALL
- wait must be in while loop (spurious wakeups)
- interrupt doesn't stop a thread - it sets a flag / throws InterruptedException
```
