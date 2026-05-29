# Staff Engineer - Part 3: Concurrency Coding Problems & Classic Patterns
# These are ACTUAL coding problems asked at FAANG/top companies

## Classic Concurrency Problems (with complete solutions)

### Problem 1: Implement a Thread-Safe LRU Cache

**Asked at:** Google, Amazon, Meta, Microsoft

```java
// Requirements:
// - O(1) get and put
// - Thread-safe (multiple threads read/write concurrently)
// - Evicts least recently used when at capacity
// - get() makes entry most recently used

// APPROACH 1: ConcurrentHashMap + ConcurrentLinkedDeque (lock-free reads)
class ConcurrentLRUCache<K, V> {
    private final int capacity;
    private final ConcurrentHashMap<K, V> map;
    private final ConcurrentLinkedDeque<K> deque;  // Order tracking
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    
    ConcurrentLRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new ConcurrentHashMap<>(capacity);
        this.deque = new ConcurrentLinkedDeque<>();
    }
    
    V get(K key) {
        V value = map.get(key);
        if (value != null) {
            // Move to most recent (approximate LRU for performance)
            deque.remove(key);
            deque.addFirst(key);
        }
        return value;
    }
    
    void put(K key, V value) {
        if (map.containsKey(key)) {
            map.put(key, value);
            deque.remove(key);
            deque.addFirst(key);
        } else {
            while (map.size() >= capacity) {
                K evicted = deque.removeLast();
                map.remove(evicted);
            }
            map.put(key, value);
            deque.addFirst(key);
        }
    }
}

// APPROACH 2: Striped locking (better concurrency)
class StripedLRUCache<K, V> {
    private static final int STRIPES = 16;
    private final LRUCacheSegment<K, V>[] segments;
    
    StripedLRUCache(int totalCapacity) {
        segments = new LRUCacheSegment[STRIPES];
        int perSegment = totalCapacity / STRIPES;
        for (int i = 0; i < STRIPES; i++) {
            segments[i] = new LRUCacheSegment<>(perSegment);
        }
    }
    
    private int segmentIndex(K key) {
        return (key.hashCode() & 0x7FFFFFFF) % STRIPES;
    }
    
    V get(K key) {
        return segments[segmentIndex(key)].get(key);
    }
    
    void put(K key, V value) {
        segments[segmentIndex(key)].put(key, value);
    }
    
    // Each segment has its own lock → 16x concurrency
    static class LRUCacheSegment<K, V> {
        private final LinkedHashMap<K, V> map;
        private final ReentrantLock lock = new ReentrantLock();
        
        LRUCacheSegment(int capacity) {
            this.map = new LinkedHashMap<>(capacity, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
                    return size() > capacity;
                }
            };
        }
        
        V get(K key) {
            lock.lock();
            try {
                return map.get(key);
            } finally {
                lock.unlock();
            }
        }
        
        void put(K key, V value) {
            lock.lock();
            try {
                map.put(key, value);
            } finally {
                lock.unlock();
            }
        }
    }
}

// APPROACH 3: Using Caffeine (production-grade, best performance)
// Cache<K, V> cache = Caffeine.newBuilder()
//     .maximumSize(10_000)
//     .expireAfterWrite(10, TimeUnit.MINUTES)
//     .recordStats()
//     .build();
```

---

### Problem 2: Implement a Rate Limiter (Token Bucket / Sliding Window)

**Asked at:** Google, Uber, Stripe, Amazon

```java
// TOKEN BUCKET Rate Limiter (thread-safe)
class TokenBucketRateLimiter {
    private final int maxTokens;
    private final int refillRate;  // tokens per second
    private double availableTokens;
    private long lastRefillTimestamp;
    private final ReentrantLock lock = new ReentrantLock();
    
    TokenBucketRateLimiter(int maxTokens, int refillRate) {
        this.maxTokens = maxTokens;
        this.refillRate = refillRate;
        this.availableTokens = maxTokens;
        this.lastRefillTimestamp = System.nanoTime();
    }
    
    boolean tryAcquire() {
        return tryAcquire(1);
    }
    
    boolean tryAcquire(int tokens) {
        lock.lock();
        try {
            refill();
            if (availableTokens >= tokens) {
                availableTokens -= tokens;
                return true;
            }
            return false;
        } finally {
            lock.unlock();
        }
    }
    
    private void refill() {
        long now = System.nanoTime();
        double elapsed = (now - lastRefillTimestamp) / 1_000_000_000.0;
        double tokensToAdd = elapsed * refillRate;
        availableTokens = Math.min(maxTokens, availableTokens + tokensToAdd);
        lastRefillTimestamp = now;
    }
}

// SLIDING WINDOW Rate Limiter (more accurate)
class SlidingWindowRateLimiter {
    private final int maxRequests;
    private final long windowSizeMs;
    private final ConcurrentLinkedQueue<Long> timestamps = new ConcurrentLinkedQueue<>();
    private final AtomicInteger count = new AtomicInteger(0);
    
    SlidingWindowRateLimiter(int maxRequests, long windowSizeMs) {
        this.maxRequests = maxRequests;
        this.windowSizeMs = windowSizeMs;
    }
    
    boolean tryAcquire() {
        long now = System.currentTimeMillis();
        long windowStart = now - windowSizeMs;
        
        // Remove expired timestamps
        while (!timestamps.isEmpty() && timestamps.peek() <= windowStart) {
            timestamps.poll();
            count.decrementAndGet();
        }
        
        if (count.get() < maxRequests) {
            timestamps.offer(now);
            count.incrementAndGet();
            return true;
        }
        return false;
    }
}

// DISTRIBUTED Rate Limiter (Redis-based)
// Lua script for atomicity:
// local key = KEYS[1]
// local limit = tonumber(ARGV[1])
// local window = tonumber(ARGV[2])
// local current = redis.call('INCR', key)
// if current == 1 then redis.call('EXPIRE', key, window) end
// if current > limit then return 0 else return 1 end
```

---

### Problem 3: Print Numbers in Order Using 3 Threads (1,2,3,1,2,3...)

**Asked at:** Amazon, Meta, Bloomberg

```java
// Three threads print 1, 2, 3 in sequence repeatedly
class PrintInOrder {
    private final int n;
    private volatile int turn = 1;
    private final Object lock = new Object();
    
    PrintInOrder(int n) { this.n = n; }
    
    void printNumber(int threadId) {
        for (int i = 0; i < n; i++) {
            synchronized (lock) {
                while (turn != threadId) {
                    try { lock.wait(); } 
                    catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                }
                System.out.print(threadId);
                turn = (turn % 3) + 1;
                lock.notifyAll();
            }
        }
    }
    
    public static void main(String[] args) {
        PrintInOrder pio = new PrintInOrder(10);
        new Thread(() -> pio.printNumber(1)).start();
        new Thread(() -> pio.printNumber(2)).start();
        new Thread(() -> pio.printNumber(3)).start();
    }
}

// Using Semaphores (cleaner):
class PrintInOrderSemaphore {
    private final Semaphore sem1 = new Semaphore(1);  // Thread 1 starts
    private final Semaphore sem2 = new Semaphore(0);
    private final Semaphore sem3 = new Semaphore(0);
    
    void printFirst(int n) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            sem1.acquire();
            System.out.print("1");
            sem2.release();
        }
    }
    
    void printSecond(int n) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            sem2.acquire();
            System.out.print("2");
            sem3.release();
        }
    }
    
    void printThird(int n) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            sem3.acquire();
            System.out.print("3");
            sem1.release();
        }
    }
}
```

---

### Problem 4: Implement a Blocking Queue from Scratch

**Asked at:** Google, Amazon, Apple, Microsoft

```java
class MyBlockingQueue<E> {
    private final Object[] items;
    private int putIndex;
    private int takeIndex;
    private int count;
    
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();
    
    MyBlockingQueue(int capacity) {
        items = new Object[capacity];
    }
    
    // Blocks if queue is full
    void put(E element) throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (count == items.length) {
                notFull.await();  // Wait until space available
            }
            items[putIndex] = element;
            putIndex = (putIndex + 1) % items.length;  // Circular buffer
            count++;
            notEmpty.signal();  // Wake one waiting consumer
        } finally {
            lock.unlock();
        }
    }
    
    // Blocks if queue is empty
    @SuppressWarnings("unchecked")
    E take() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (count == 0) {
                notEmpty.await();  // Wait until item available
            }
            E element = (E) items[takeIndex];
            items[takeIndex] = null;  // Help GC
            takeIndex = (takeIndex + 1) % items.length;
            count--;
            notFull.signal();  // Wake one waiting producer
            return element;
        } finally {
            lock.unlock();
        }
    }
    
    // Non-blocking with timeout
    E poll(long timeout, TimeUnit unit) throws InterruptedException {
        long nanos = unit.toNanos(timeout);
        lock.lockInterruptibly();
        try {
            while (count == 0) {
                if (nanos <= 0) return null;
                nanos = notEmpty.awaitNanos(nanos);  // Decrements remaining time
            }
            E element = (E) items[takeIndex];
            items[takeIndex] = null;
            takeIndex = (takeIndex + 1) % items.length;
            count--;
            notFull.signal();
            return element;
        } finally {
            lock.unlock();
        }
    }
    
    int size() {
        lock.lock();
        try { return count; } 
        finally { lock.unlock(); }
    }
}
```

---

### Problem 5: Implement ReadWriteLock from Scratch

**Asked at:** Google, Microsoft, Bloomberg

```java
class SimpleReadWriteLock {
    private int readers = 0;
    private int writers = 0;
    private int writeRequests = 0;
    
    synchronized void lockRead() throws InterruptedException {
        while (writers > 0 || writeRequests > 0) {
            wait();  // Wait if there's a writer or pending write request
            // writeRequests check prevents writer starvation!
        }
        readers++;
    }
    
    synchronized void unlockRead() {
        readers--;
        notifyAll();  // Wake waiting writers
    }
    
    synchronized void lockWrite() throws InterruptedException {
        writeRequests++;
        try {
            while (readers > 0 || writers > 0) {
                wait();  // Wait for all readers and current writer to finish
            }
            writers++;
        } finally {
            writeRequests--;
        }
    }
    
    synchronized void unlockWrite() {
        writers--;
        notifyAll();  // Wake all waiting readers and writers
    }
}

// Usage:
SimpleReadWriteLock rwLock = new SimpleReadWriteLock();
// Reader:
rwLock.lockRead();
try { readData(); }
finally { rwLock.unlockRead(); }
// Writer:
rwLock.lockWrite();
try { writeData(); }
finally { rwLock.unlockWrite(); }
```

---

### Problem 6: Dining Philosophers (Deadlock-Free)

**Asked at:** Google, Amazon, Uber

```java
// 5 philosophers, 5 forks, each needs 2 adjacent forks to eat
// Challenge: Avoid deadlock and starvation

// SOLUTION 1: Resource ordering (break circular wait)
class DiningPhilosophers {
    private final ReentrantLock[] forks = new ReentrantLock[5];
    
    DiningPhilosophers() {
        for (int i = 0; i < 5; i++) {
            forks[i] = new ReentrantLock();
        }
    }
    
    void eat(int philosopher) {
        int left = philosopher;
        int right = (philosopher + 1) % 5;
        
        // Always lock lower-numbered fork first (breaks circular wait!)
        int first = Math.min(left, right);
        int second = Math.max(left, right);
        
        forks[first].lock();
        try {
            forks[second].lock();
            try {
                doEat(philosopher);
            } finally {
                forks[second].unlock();
            }
        } finally {
            forks[first].unlock();
        }
    }
}

// SOLUTION 2: Semaphore limiting concurrent diners
class DiningPhilosophersV2 {
    private final Semaphore[] forks = new Semaphore[5];
    private final Semaphore maxDiners = new Semaphore(4);  // Only 4 can try at once!
    
    DiningPhilosophersV2() {
        for (int i = 0; i < 5; i++) forks[i] = new Semaphore(1);
    }
    
    void eat(int philosopher) throws InterruptedException {
        int left = philosopher;
        int right = (philosopher + 1) % 5;
        
        maxDiners.acquire();  // At most 4 philosophers try → no deadlock!
        try {
            forks[left].acquire();
            forks[right].acquire();
            doEat(philosopher);
            forks[right].release();
            forks[left].release();
        } finally {
            maxDiners.release();
        }
    }
}
```

---

### Problem 7: Implement a Thread-Safe Singleton with Lazy Initialization

**Asked at:** Every company

```java
// Best approach: Initialization-on-Demand Holder
class Singleton {
    private Singleton() {
        // Prevent reflection attack:
        if (Holder.INSTANCE != null) {
            throw new IllegalStateException("Already instantiated!");
        }
    }
    
    private static class Holder {
        private static final Singleton INSTANCE = new Singleton();
    }
    
    public static Singleton getInstance() {
        return Holder.INSTANCE;
    }
    
    // Prevent deserialization creating new instance:
    private Object readResolve() {
        return Holder.INSTANCE;
    }
}
```

---

### Problem 8: Implement a CountDownLatch from Scratch

**Asked at:** Amazon, Microsoft

```java
class MyCountDownLatch {
    private int count;
    
    MyCountDownLatch(int count) {
        if (count < 0) throw new IllegalArgumentException();
        this.count = count;
    }
    
    synchronized void await() throws InterruptedException {
        while (count > 0) {
            wait();
        }
    }
    
    synchronized boolean await(long timeout, TimeUnit unit) throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (count > 0) {
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) return false;
            wait(remaining / 1_000_000, (int)(remaining % 1_000_000));
        }
        return true;
    }
    
    synchronized void countDown() {
        if (count > 0) {
            count--;
            if (count == 0) {
                notifyAll();  // Wake all waiting threads
            }
        }
    }
    
    synchronized long getCount() {
        return count;
    }
}
```

---

### Problem 9: Implement a Thread Pool from Scratch

**Asked at:** Google, Amazon, Meta

```java
class SimpleThreadPool {
    private final BlockingQueue<Runnable> taskQueue;
    private final List<Worker> workers;
    private volatile boolean isShutdown = false;
    
    SimpleThreadPool(int poolSize, int queueCapacity) {
        this.taskQueue = new LinkedBlockingQueue<>(queueCapacity);
        this.workers = new ArrayList<>(poolSize);
        
        for (int i = 0; i < poolSize; i++) {
            Worker worker = new Worker("pool-thread-" + i);
            workers.add(worker);
            worker.start();
        }
    }
    
    void submit(Runnable task) {
        if (isShutdown) throw new RejectedExecutionException("Pool is shutdown");
        try {
            taskQueue.put(task);  // Blocks if queue full (backpressure!)
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
    
    void shutdown() {
        isShutdown = true;
        for (Worker worker : workers) {
            worker.interrupt();
        }
    }
    
    void awaitTermination(long timeout, TimeUnit unit) throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        for (Worker worker : workers) {
            long remaining = deadline - System.nanoTime();
            if (remaining > 0) {
                worker.join(remaining / 1_000_000);
            }
        }
    }
    
    private class Worker extends Thread {
        Worker(String name) { super(name); }
        
        @Override
        public void run() {
            while (!isShutdown || !taskQueue.isEmpty()) {
                try {
                    Runnable task = taskQueue.poll(1, TimeUnit.SECONDS);
                    if (task != null) {
                        task.run();
                    }
                } catch (InterruptedException e) {
                    // Check isShutdown on next iteration
                } catch (Exception e) {
                    // Log but don't kill the worker
                    System.err.println(getName() + " task failed: " + e.getMessage());
                }
            }
        }
    }
}
```

---

### Problem 10: Implement a Bounded Buffer (Multiple Producers, Multiple Consumers)

**Asked at:** Amazon, Goldman Sachs, Morgan Stanley

```java
class BoundedBuffer<E> {
    private final E[] buffer;
    private int head, tail, count;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();
    
    @SuppressWarnings("unchecked")
    BoundedBuffer(int capacity) {
        buffer = (E[]) new Object[capacity];
    }
    
    void produce(E item) throws InterruptedException {
        lock.lock();
        try {
            while (count == buffer.length) {
                notFull.await();
            }
            buffer[tail] = item;
            tail = (tail + 1) % buffer.length;
            count++;
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
    }
    
    E consume() throws InterruptedException {
        lock.lock();
        try {
            while (count == 0) {
                notEmpty.await();
            }
            E item = buffer[head];
            buffer[head] = null;
            head = (head + 1) % buffer.length;
            count--;
            notFull.signal();
            return item;
        } finally {
            lock.unlock();
        }
    }
}
```

---

### Problem 11: Implement a Deadlock Detector

**Asked at:** Google, Microsoft

```java
class DeadlockDetector {
    private final Map<Long, Set<Long>> waitForGraph = new ConcurrentHashMap<>();
    // Key: threadId waiting, Value: set of threadIds it's waiting for
    
    void threadWaitsFor(long waiter, long holder) {
        waitForGraph.computeIfAbsent(waiter, k -> ConcurrentHashMap.newKeySet())
                    .add(holder);
    }
    
    void threadReleased(long waiter) {
        waitForGraph.remove(waiter);
    }
    
    // Detect cycle using DFS
    boolean hasDeadlock() {
        Set<Long> visited = new HashSet<>();
        Set<Long> inStack = new HashSet<>();
        
        for (Long thread : waitForGraph.keySet()) {
            if (hasCycle(thread, visited, inStack)) {
                return true;
            }
        }
        return false;
    }
    
    private boolean hasCycle(Long current, Set<Long> visited, Set<Long> inStack) {
        if (inStack.contains(current)) return true;  // Cycle!
        if (visited.contains(current)) return false;
        
        visited.add(current);
        inStack.add(current);
        
        Set<Long> dependencies = waitForGraph.getOrDefault(current, Set.of());
        for (Long dep : dependencies) {
            if (hasCycle(dep, visited, inStack)) return true;
        }
        
        inStack.remove(current);
        return false;
    }
    
    // Using JMX (built-in):
    static long[] detectDeadlocks() {
        ThreadMXBean bean = ManagementFactory.getThreadMXBean();
        return bean.findDeadlockedThreads();  // Returns null if no deadlock
    }
}
```

---

### Problem 12: Implement Async Task Scheduler (ScheduledExecutor)

**Asked at:** Amazon, Apple, Uber

```java
class SimpleScheduler {
    private final PriorityBlockingQueue<ScheduledTask> queue = 
        new PriorityBlockingQueue<>();
    private final Thread schedulerThread;
    private volatile boolean running = true;
    
    SimpleScheduler() {
        schedulerThread = new Thread(this::run, "scheduler");
        schedulerThread.setDaemon(true);
        schedulerThread.start();
    }
    
    void schedule(Runnable task, long delayMs) {
        long executeAt = System.currentTimeMillis() + delayMs;
        queue.offer(new ScheduledTask(task, executeAt));
    }
    
    void scheduleAtFixedRate(Runnable task, long initialDelay, long periodMs) {
        long executeAt = System.currentTimeMillis() + initialDelay;
        queue.offer(new ScheduledTask(task, executeAt, periodMs, true));
    }
    
    private void run() {
        while (running) {
            try {
                ScheduledTask task = queue.peek();
                if (task == null) {
                    Thread.sleep(10);
                    continue;
                }
                
                long now = System.currentTimeMillis();
                if (task.executeAt <= now) {
                    queue.poll();
                    try {
                        task.runnable.run();
                    } catch (Exception e) {
                        System.err.println("Task failed: " + e.getMessage());
                    }
                    // Reschedule if periodic
                    if (task.periodic) {
                        task.executeAt = now + task.periodMs;
                        queue.offer(task);
                    }
                } else {
                    Thread.sleep(Math.min(task.executeAt - now, 100));
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
    
    static class ScheduledTask implements Comparable<ScheduledTask> {
        final Runnable runnable;
        long executeAt;
        final long periodMs;
        final boolean periodic;
        
        ScheduledTask(Runnable r, long executeAt) {
            this(r, executeAt, 0, false);
        }
        
        ScheduledTask(Runnable r, long executeAt, long periodMs, boolean periodic) {
            this.runnable = r;
            this.executeAt = executeAt;
            this.periodMs = periodMs;
            this.periodic = periodic;
        }
        
        @Override
        public int compareTo(ScheduledTask other) {
            return Long.compare(this.executeAt, other.executeAt);
        }
    }
    
    void shutdown() {
        running = false;
        schedulerThread.interrupt();
    }
}
```

---

### Problem 13: Implement a Concurrent HashMap (Simplified)

**Asked at:** Google, Amazon

```java
class SimpleConcurrentMap<K, V> {
    private static final int SEGMENTS = 16;
    private final Segment<K, V>[] segments;
    
    @SuppressWarnings("unchecked")
    SimpleConcurrentMap() {
        segments = new Segment[SEGMENTS];
        for (int i = 0; i < SEGMENTS; i++) {
            segments[i] = new Segment<>();
        }
    }
    
    private int segmentFor(K key) {
        return (key.hashCode() & 0x7FFFFFFF) % SEGMENTS;
    }
    
    V get(K key) {
        return segments[segmentFor(key)].get(key);
    }
    
    void put(K key, V value) {
        segments[segmentFor(key)].put(key, value);
    }
    
    V remove(K key) {
        return segments[segmentFor(key)].remove(key);
    }
    
    static class Segment<K, V> {
        private final Map<K, V> map = new HashMap<>();
        private final ReentrantLock lock = new ReentrantLock();
        
        V get(K key) {
            lock.lock();
            try { return map.get(key); }
            finally { lock.unlock(); }
        }
        
        void put(K key, V value) {
            lock.lock();
            try { map.put(key, value); }
            finally { lock.unlock(); }
        }
        
        V remove(K key) {
            lock.lock();
            try { return map.remove(key); }
            finally { lock.unlock(); }
        }
    }
}
```

---

### Problem 14: FizzBuzz Multithreaded (LeetCode 1195)

**Asked at:** Meta, Amazon

```java
class FizzBuzzMultithreaded {
    private int n;
    private int current = 1;
    
    FizzBuzzMultithreaded(int n) { this.n = n; }
    
    synchronized void fizz() throws InterruptedException {
        while (current <= n) {
            while (current <= n && !(current % 3 == 0 && current % 5 != 0)) {
                wait();
            }
            if (current > n) return;
            System.out.print("fizz ");
            current++;
            notifyAll();
        }
    }
    
    synchronized void buzz() throws InterruptedException {
        while (current <= n) {
            while (current <= n && !(current % 5 == 0 && current % 3 != 0)) {
                wait();
            }
            if (current > n) return;
            System.out.print("buzz ");
            current++;
            notifyAll();
        }
    }
    
    synchronized void fizzbuzz() throws InterruptedException {
        while (current <= n) {
            while (current <= n && !(current % 15 == 0)) {
                wait();
            }
            if (current > n) return;
            System.out.print("fizzbuzz ");
            current++;
            notifyAll();
        }
    }
    
    synchronized void number() throws InterruptedException {
        while (current <= n) {
            while (current <= n && (current % 3 == 0 || current % 5 == 0)) {
                wait();
            }
            if (current > n) return;
            System.out.print(current + " ");
            current++;
            notifyAll();
        }
    }
}
```

---

### Problem 15: Implement H2O (LeetCode 1117)

**Asked at:** Google, Meta

```java
// Two hydrogen threads and one oxygen thread must synchronize
// to produce water molecules (H2O, H2O, H2O...)
class H2O {
    private final Semaphore hSem = new Semaphore(2);  // Allow 2 hydrogen
    private final Semaphore oSem = new Semaphore(0);  // Oxygen waits
    private final CyclicBarrier barrier = new CyclicBarrier(3, () -> {
        // After H, H, O arrive → release next batch
        hSem.release(2);
    });
    
    void hydrogen(Runnable releaseHydrogen) throws InterruptedException {
        hSem.acquire();
        try {
            barrier.await();
            releaseHydrogen.run();
        } catch (BrokenBarrierException e) {
            Thread.currentThread().interrupt();
        }
    }
    
    void oxygen(Runnable releaseOxygen) throws InterruptedException {
        oSem.acquire();
        try {
            barrier.await();
            releaseOxygen.run();
        } catch (BrokenBarrierException e) {
            Thread.currentThread().interrupt();
        }
    }
    
    // Alternative: Use semaphores only
    private final Semaphore h = new Semaphore(2);
    private final Semaphore o = new Semaphore(1);
    private final CyclicBarrier b = new CyclicBarrier(3);
    
    void hydrogen2(Runnable release) throws Exception {
        h.acquire();
        b.await();
        release.run();
        h.release();
    }
    
    void oxygen2(Runnable release) throws Exception {
        o.acquire();
        b.await();
        release.run();
        o.release();
    }
}
```

---

### Problem 16: Design a Thread-Safe Event Bus / Pub-Sub

**Asked at:** Amazon, Google, LinkedIn

```java
class EventBus {
    private final Map<Class<?>, Set<EventHandler<?>>> handlers = new ConcurrentHashMap<>();
    private final ExecutorService executor;
    
    EventBus(ExecutorService executor) {
        this.executor = executor;
    }
    
    <T> void subscribe(Class<T> eventType, EventHandler<T> handler) {
        handlers.computeIfAbsent(eventType, k -> ConcurrentHashMap.newKeySet())
                .add(handler);
    }
    
    <T> void unsubscribe(Class<T> eventType, EventHandler<T> handler) {
        Set<EventHandler<?>> set = handlers.get(eventType);
        if (set != null) set.remove(handler);
    }
    
    @SuppressWarnings("unchecked")
    <T> void publish(T event) {
        Set<EventHandler<?>> set = handlers.get(event.getClass());
        if (set == null) return;
        
        for (EventHandler<?> handler : set) {
            executor.submit(() -> {
                try {
                    ((EventHandler<T>) handler).handle(event);
                } catch (Exception e) {
                    System.err.println("Handler failed: " + e.getMessage());
                }
            });
        }
    }
    
    @FunctionalInterface
    interface EventHandler<T> {
        void handle(T event);
    }
}

// Usage:
EventBus bus = new EventBus(Executors.newFixedThreadPool(4));
bus.subscribe(OrderCreatedEvent.class, event -> sendEmail(event));
bus.subscribe(OrderCreatedEvent.class, event -> updateInventory(event));
bus.publish(new OrderCreatedEvent(orderId));
```

---

### Problem 17: Implement a Non-Blocking Stack using CAS

**Asked at:** Google, Jane Street, HRT

```java
// See Treiber Stack in Part 1 - here with ABA protection
class ABASafeStack<E> {
    private final AtomicStampedReference<Node<E>> head = 
        new AtomicStampedReference<>(null, 0);
    
    static class Node<E> {
        final E value;
        Node<E> next;
        Node(E value) { this.value = value; }
    }
    
    void push(E value) {
        Node<E> newNode = new Node<>(value);
        int[] stampHolder = new int[1];
        Node<E> oldHead;
        do {
            oldHead = head.get(stampHolder);
            newNode.next = oldHead;
        } while (!head.compareAndSet(oldHead, newNode, stampHolder[0], stampHolder[0] + 1));
    }
    
    E pop() {
        int[] stampHolder = new int[1];
        Node<E> oldHead;
        Node<E> newHead;
        do {
            oldHead = head.get(stampHolder);
            if (oldHead == null) return null;
            newHead = oldHead.next;
        } while (!head.compareAndSet(oldHead, newHead, stampHolder[0], stampHolder[0] + 1));
        return oldHead.value;
    }
}
```

---

### Problem 18: Implement Future/Promise from Scratch

**Asked at:** Amazon, Meta, Microsoft

```java
class MyFuture<V> {
    private volatile V result;
    private volatile Throwable exception;
    private volatile boolean done;
    private final CountDownLatch latch = new CountDownLatch(1);
    private final List<Consumer<V>> successCallbacks = new CopyOnWriteArrayList<>();
    private final List<Consumer<Throwable>> errorCallbacks = new CopyOnWriteArrayList<>();
    
    // Complete successfully
    void complete(V value) {
        if (done) throw new IllegalStateException("Already completed");
        this.result = value;
        this.done = true;
        latch.countDown();
        successCallbacks.forEach(cb -> cb.accept(value));
    }
    
    // Complete with error
    void completeExceptionally(Throwable ex) {
        if (done) throw new IllegalStateException("Already completed");
        this.exception = ex;
        this.done = true;
        latch.countDown();
        errorCallbacks.forEach(cb -> cb.accept(ex));
    }
    
    // Blocking get
    V get() throws InterruptedException, ExecutionException {
        latch.await();
        if (exception != null) throw new ExecutionException(exception);
        return result;
    }
    
    V get(long timeout, TimeUnit unit) throws InterruptedException, ExecutionException, TimeoutException {
        if (!latch.await(timeout, unit)) throw new TimeoutException();
        if (exception != null) throw new ExecutionException(exception);
        return result;
    }
    
    boolean isDone() { return done; }
    
    // Callback-based (non-blocking)
    MyFuture<V> onSuccess(Consumer<V> callback) {
        if (done && exception == null) callback.accept(result);
        else successCallbacks.add(callback);
        return this;
    }
    
    MyFuture<V> onError(Consumer<Throwable> callback) {
        if (done && exception != null) callback.accept(exception);
        else errorCallbacks.add(callback);
        return this;
    }
    
    // Transform (map)
    <U> MyFuture<U> map(Function<V, U> mapper) {
        MyFuture<U> next = new MyFuture<>();
        onSuccess(v -> next.complete(mapper.apply(v)));
        onError(next::completeExceptionally);
        return next;
    }
}
```

---

