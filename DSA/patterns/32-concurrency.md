# 32. Concurrency Patterns

## Java Concurrency Primitives Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PRIMITIVE            │ PURPOSE                  │ KEY PROPERTY              │
├─────────────────────────────────────────────────────────────────────────────┤
│ synchronized         │ Mutual exclusion         │ Reentrant, implicit lock  │
│ ReentrantLock        │ Explicit mutual exclusion│ Fairness option, tryLock  │
│ Semaphore            │ Permit-based access      │ N permits, acquire/release│
│ CountDownLatch       │ One-shot barrier         │ Count to zero, not reset  │
│ CyclicBarrier        │ Reusable barrier         │ All parties arrive, reset │
│ volatile             │ Visibility guarantee     │ No atomicity for compound │
│ AtomicInteger        │ Lock-free CAS ops        │ compareAndSet, increment  │
│ Condition            │ Selective notification   │ await/signal on lock      │
│ Phaser               │ Flexible barrier         │ Dynamic party count       │
│ BlockingQueue        │ Thread-safe queue        │ Blocking put/take         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Decision Flowchart: Which Primitive to Use

```
Need to synchronize threads?
│
├─ Ordering/sequencing threads? ──→ Need one-shot? ──→ CountDownLatch
│                                    └─ Reusable?  ──→ CyclicBarrier / Phaser
│
├─ Mutual exclusion?
│   ├─ Simple critical section ──→ synchronized
│   ├─ Need tryLock/timeout   ──→ ReentrantLock
│   └─ Need multiple conditions──→ ReentrantLock + Condition
│
├─ Limiting concurrency (N threads)? ──→ Semaphore(N)
│
├─ Alternating between threads? ──→ Semaphore pair (permits=0/1)
│
├─ Producer-Consumer? ──→ BlockingQueue
│   └─ Need bounded? ──→ ArrayBlockingQueue / Semaphore-bounded
│
├─ Single flag/visibility? ──→ volatile boolean
│
└─ Counter without lock? ──→ AtomicInteger
```

---

## 1. Print in Order (LC 1114)

### Signal
Three threads call `first()`, `second()`, `third()` — must execute in order regardless of scheduling.

### Visualization
```
Thread A: ──first()──signal──────────────────────────────
Thread B: ──────────wait──second()──signal────────────────
Thread C: ──────────────────────────wait──third()────────
Timeline:  ═══════════════════════════════════════════════►
Output:    "first"         "second"         "third"
```

### Template A: CountDownLatch

```java
class Foo {
    private CountDownLatch latch1 = new CountDownLatch(1);
    private CountDownLatch latch2 = new CountDownLatch(1);

    public void first(Runnable printFirst) throws InterruptedException {
        printFirst.run();
        latch1.countDown();  // Signal second can proceed
    }

    public void second(Runnable printSecond) throws InterruptedException {
        latch1.await();      // Wait for first
        printSecond.run();
        latch2.countDown();  // Signal third can proceed
    }

    public void third(Runnable printThird) throws InterruptedException {
        latch2.await();      // Wait for second
        printThird.run();
    }
}
```

### Template B: Semaphore

```java
class Foo {
    private Semaphore sem2 = new Semaphore(0);
    private Semaphore sem3 = new Semaphore(0);

    public void first(Runnable printFirst) throws InterruptedException {
        printFirst.run();
        sem2.release();
    }

    public void second(Runnable printSecond) throws InterruptedException {
        sem2.acquire();
        printSecond.run();
        sem3.release();
    }

    public void third(Runnable printThird) throws InterruptedException {
        sem3.acquire();
        printThird.run();
    }
}
```

### Template C: volatile flags

```java
class Foo {
    private volatile int flag = 0;

    public void first(Runnable printFirst) throws InterruptedException {
        printFirst.run();
        flag = 1;
    }

    public void second(Runnable printSecond) throws InterruptedException {
        while (flag != 1);  // Spin-wait (CPU intensive)
        printSecond.run();
        flag = 2;
    }

    public void third(Runnable printThird) throws InterruptedException {
        while (flag != 2);
        printThird.run();
    }
}
```

### Complexity
- Time: O(1) per thread (excluding wait time)
- Space: O(1)

### Trade-offs
| Approach       | Pros                     | Cons                          |
|----------------|--------------------------|-------------------------------|
| CountDownLatch | Clean, no spin           | One-shot only                 |
| Semaphore      | Flexible, reusable       | Slightly more overhead        |
| volatile       | No library dependency    | Spin-wait wastes CPU          |

---

## 2. Print FooBar Alternately (LC 1115)

### Signal
Two threads must alternate: one prints "foo", the other prints "bar", n times total → "foobarfoobar..."

### Visualization
```
Thread Foo: ──print──wait──────print──wait──────print──
Thread Bar: ──wait──────print──wait──────print──wait───print──
Output:      "foo"    "bar"   "foo"    "bar"   "foo"   "bar"
```

### Template: Semaphore Pair

```java
class FooBar {
    private int n;
    private Semaphore fooSem = new Semaphore(1);  // Foo goes first
    private Semaphore barSem = new Semaphore(0);

    public FooBar(int n) { this.n = n; }

    public void foo(Runnable printFoo) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            fooSem.acquire();   // Wait for permission to print foo
            printFoo.run();
            barSem.release();   // Signal bar to print
        }
    }

    public void bar(Runnable printBar) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            barSem.acquire();   // Wait for permission to print bar
            printBar.run();
            fooSem.release();   // Signal foo to print
        }
    }
}
```

### Key Insight
**Semaphore pair creates a ping-pong pattern**: each thread releases the other's semaphore after completing its work.

### Complexity
- Time: O(n) per thread
- Space: O(1)

---

## 3. Print Zero Even Odd (LC 1116)

### Signal
Three threads: one prints 0, one prints even numbers, one prints odd numbers.
Output for n=5: `0102030405`

### Visualization
```
Thread Zero: print(0)─rel─wait─print(0)─rel─wait─print(0)─rel─wait─...
Thread Odd:  ─────────wait─print(1)─rel──────────wait─print(3)─rel──...
Thread Even: ─────────────────────────wait─print(2)─rel──────────────...
Output:       0        1              0      2            0      3    ...
```

### Template: Three Semaphores

```java
class ZeroEvenOdd {
    private int n;
    private Semaphore zeroSem = new Semaphore(1);  // Zero starts
    private Semaphore oddSem = new Semaphore(0);
    private Semaphore evenSem = new Semaphore(0);

    public ZeroEvenOdd(int n) { this.n = n; }

    public void zero(IntConsumer printNumber) throws InterruptedException {
        for (int i = 1; i <= n; i++) {
            zeroSem.acquire();
            printNumber.accept(0);
            if (i % 2 == 1) oddSem.release();   // Next is odd
            else evenSem.release();              // Next is even
        }
    }

    public void odd(IntConsumer printNumber) throws InterruptedException {
        for (int i = 1; i <= n; i += 2) {
            oddSem.acquire();
            printNumber.accept(i);
            zeroSem.release();
        }
    }

    public void even(IntConsumer printNumber) throws InterruptedException {
        for (int i = 2; i <= n; i += 2) {
            evenSem.acquire();
            printNumber.accept(i);
            zeroSem.release();
        }
    }
}
```

### Key Insight
Zero thread acts as a **dispatcher** — it decides which thread to wake based on the current number parity.

### Complexity
- Time: O(n) total across all threads
- Space: O(1)

---

## 4. Building H2O (LC 1117)

### Signal
Multiple threads call `hydrogen()` or `oxygen()`. Must form groups of H2O (2 hydrogen + 1 oxygen) before any thread in a group can proceed.

### Visualization
```
H threads: H─wait─┐    H─wait─┐    H─wait─┐
                   ├─BARRIER──►    ├─BARRIER──►
O threads:    O─wait─┘         O─wait─┘

Each barrier releases exactly 2H + 1O together
```

### Template: Semaphore + CyclicBarrier

```java
class H2O {
    private Semaphore hSem = new Semaphore(2);  // Max 2 H at a time
    private Semaphore oSem = new Semaphore(1);  // Max 1 O at a time
    private CyclicBarrier barrier = new CyclicBarrier(3);  // Wait for 3

    public void hydrogen(Runnable releaseHydrogen) throws InterruptedException {
        hSem.acquire();
        try {
            barrier.await();  // Wait until 2H + 1O arrive
        } catch (BrokenBarrierException e) {}
        releaseHydrogen.run();
        hSem.release();
    }

    public void oxygen(Runnable releaseOxygen) throws InterruptedException {
        oSem.acquire();
        try {
            barrier.await();
        } catch (BrokenBarrierException e) {}
        releaseOxygen.run();
        oSem.release();
    }
}
```

### Key Insight
- **Semaphores** enforce the 2:1 ratio (only 2H and 1O can enter at a time)
- **CyclicBarrier(3)** ensures all 3 arrive before any proceeds
- Barrier is reusable (cyclic) so multiple H2O molecules form sequentially

### Complexity
- Time: O(1) per thread (excluding wait)
- Space: O(1)

---

## 5. Dining Philosophers (LC 1226)

### Signal
5 philosophers around a table, each needs 2 forks to eat. Prevent deadlock.

### Visualization
```
        P0
     f4    f0
   P4        P1
     f3    f1
      P3──P2
         f2

Deadlock scenario (all pick left fork): P0→f0, P1→f1, P2→f2, P3→f3, P4→f4
                                         All wait for right fork → DEADLOCK

Resource ordering fix: Always pick lower-numbered fork first
P4 picks f0 before f4 (breaks the cycle!)
```

### Template: Resource Ordering

```java
class DiningPhilosophers {
    private ReentrantLock[] forks = new ReentrantLock[5];

    public DiningPhilosophers() {
        for (int i = 0; i < 5; i++) forks[i] = new ReentrantLock();
    }

    public void wantsToEat(int philosopher,
                           Runnable pickLeftFork, Runnable pickRightFork,
                           Runnable eat,
                           Runnable putLeftFork, Runnable putRightFork)
                           throws InterruptedException {
        int left = philosopher;
        int right = (philosopher + 1) % 5;

        // Resource ordering: always lock lower-numbered fork first
        int first = Math.min(left, right);
        int second = Math.max(left, right);

        forks[first].lock();
        forks[second].lock();
        try {
            pickLeftFork.run();
            pickRightFork.run();
            eat.run();
            putLeftFork.run();
            putRightFork.run();
        } finally {
            forks[second].unlock();
            forks[first].unlock();
        }
    }
}
```

### Alternative: Limit Concurrency (at most 4 eat simultaneously)

```java
class DiningPhilosophers {
    private ReentrantLock[] forks = new ReentrantLock[5];
    private Semaphore limit = new Semaphore(4);  // At most 4 try to eat

    public void wantsToEat(int philosopher, ...) throws InterruptedException {
        int left = philosopher;
        int right = (philosopher + 1) % 5;

        limit.acquire();  // Prevents 5th philosopher from trying
        forks[left].lock();
        forks[right].lock();
        try {
            // pick, eat, put
        } finally {
            forks[right].unlock();
            forks[left].unlock();
            limit.release();
        }
    }
}
```

### Why Resource Ordering Works
- Deadlock requires a **circular wait**
- By ordering lock acquisition (always lower ID first), no cycle can form
- Philosopher 4 tries to lock fork 0 before fork 4 → breaks the ring

### Complexity
- Time: O(1) per eat operation
- Space: O(1) (5 forks is constant)

---

## 6. Bounded Blocking Queue (LC 1188)

### Signal
Implement a thread-safe queue with fixed capacity. `enqueue` blocks when full, `dequeue` blocks when empty.

### Visualization
```
Producer ──enqueue──►┌─────────────────┐──dequeue──► Consumer
                     │ [1] [2] [3] [4] │
     blocks if full  └─────────────────┘  blocks if empty
                      capacity = 4
```

### Template A: ReentrantLock + Two Conditions

```java
class BoundedBlockingQueue {
    private Queue<Integer> queue = new LinkedList<>();
    private int capacity;
    private ReentrantLock lock = new ReentrantLock();
    private Condition notFull = lock.newCondition();
    private Condition notEmpty = lock.newCondition();

    public BoundedBlockingQueue(int capacity) {
        this.capacity = capacity;
    }

    public void enqueue(int element) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) {
                notFull.await();  // Wait until space available
            }
            queue.offer(element);
            notEmpty.signal();    // Wake a waiting consumer
        } finally {
            lock.unlock();
        }
    }

    public int dequeue() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) {
                notEmpty.await();  // Wait until element available
            }
            int val = queue.poll();
            notFull.signal();      // Wake a waiting producer
            return val;
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try { return queue.size(); }
        finally { lock.unlock(); }
    }
}
```

### Template B: Semaphore-based

```java
class BoundedBlockingQueue {
    private Queue<Integer> queue = new LinkedList<>();
    private Semaphore enqSem;    // Tracks empty slots
    private Semaphore deqSem;    // Tracks filled slots
    private ReentrantLock lock = new ReentrantLock();

    public BoundedBlockingQueue(int capacity) {
        enqSem = new Semaphore(capacity);  // capacity empty slots
        deqSem = new Semaphore(0);         // 0 filled slots
    }

    public void enqueue(int element) throws InterruptedException {
        enqSem.acquire();        // Wait for empty slot
        lock.lock();
        try { queue.offer(element); }
        finally { lock.unlock(); }
        deqSem.release();        // Signal filled slot available
    }

    public int dequeue() throws InterruptedException {
        deqSem.acquire();        // Wait for filled slot
        lock.lock();
        int val;
        try { val = queue.poll(); }
        finally { lock.unlock(); }
        enqSem.release();        // Signal empty slot available
        return val;
    }
}
```

### Key Insight
- **Two conditions** (notFull/notEmpty) enable selective waking — producers only wake consumers and vice versa
- **Semaphore version** separates capacity control (semaphores) from data structure protection (lock)
- Always use `while` loop for condition checks (spurious wakeups)

### Complexity
- Time: O(1) per operation (amortized)
- Space: O(capacity)

---

## 7. Read-Write Lock Pattern

### Signal
Multiple readers can access simultaneously, but writers need exclusive access. Readers and writers contend for the same resource.

### Visualization
```
State: IDLE ──Reader arrives──► READING (count=1)
                                  │ Reader arrives → READING (count=2)
                                  │ Reader leaves → READING (count=1)
                                  │ Reader leaves → IDLE
                                  │ Writer arrives → WAITS until count=0

State: IDLE ──Writer arrives──► WRITING (exclusive)
                                  │ All readers/writers wait
                                  │ Writer done → IDLE
```

### Template: Custom Read-Write Lock

```java
class ReadWriteLock {
    private int readers = 0;
    private boolean writing = false;
    private ReentrantLock lock = new ReentrantLock();
    private Condition canRead = lock.newCondition();
    private Condition canWrite = lock.newCondition();

    public void lockRead() throws InterruptedException {
        lock.lock();
        try {
            while (writing) canRead.await();
            readers++;
        } finally {
            lock.unlock();
        }
    }

    public void unlockRead() {
        lock.lock();
        try {
            readers--;
            if (readers == 0) canWrite.signal();  // Last reader signals writer
        } finally {
            lock.unlock();
        }
    }

    public void lockWrite() throws InterruptedException {
        lock.lock();
        try {
            while (writing || readers > 0) canWrite.await();
            writing = true;
        } finally {
            lock.unlock();
        }
    }

    public void unlockWrite() {
        lock.lock();
        try {
            writing = false;
            canRead.signalAll();  // Wake all waiting readers
            canWrite.signal();    // Wake one waiting writer
        } finally {
            lock.unlock();
        }
    }
}
```

### Using Java's Built-in ReentrantReadWriteLock

```java
class ThreadSafeCache<K, V> {
    private Map<K, V> map = new HashMap<>();
    private ReadWriteLock rwLock = new ReentrantReadWriteLock();

    public V get(K key) {
        rwLock.readLock().lock();
        try { return map.get(key); }
        finally { rwLock.readLock().unlock(); }
    }

    public void put(K key, V value) {
        rwLock.writeLock().lock();
        try { map.put(key, value); }
        finally { rwLock.writeLock().unlock(); }
    }
}
```

### Pitfall: Writer Starvation
If readers arrive continuously, writer may never get access. Solutions:
- Fair mode: `new ReentrantReadWriteLock(true)` — FIFO ordering
- Writer-preference: block new readers when writer is waiting

### Complexity
- Time: O(1) for lock/unlock
- Space: O(1)

---

## 8. Producer-Consumer (Classic Pattern)

### Signal
Producers generate items, consumers process them. Decouple production rate from consumption rate using a buffer.

### Visualization
```
Producer 1 ──►┌──────────────────┐──► Consumer 1
Producer 2 ──►│  BlockingQueue   │──► Consumer 2
Producer 3 ──►└──────────────────┘──► Consumer 3
               Buffer decouples
               production/consumption
```

### Template A: BlockingQueue

```java
class ProducerConsumer {
    private BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(10);
    private volatile boolean running = true;

    class Producer implements Runnable {
        public void run() {
            try {
                while (running) {
                    int item = produce();
                    queue.put(item);  // Blocks if full
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    class Consumer implements Runnable {
        public void run() {
            try {
                while (running || !queue.isEmpty()) {
                    Integer item = queue.poll(1, TimeUnit.SECONDS);
                    if (item != null) consume(item);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}
```

### Template B: wait/notify (Low-level)

```java
class ProducerConsumer {
    private Queue<Integer> queue = new LinkedList<>();
    private int capacity = 10;
    private final Object lock = new Object();

    public void produce(int item) throws InterruptedException {
        synchronized (lock) {
            while (queue.size() == capacity) {
                lock.wait();     // Release lock and wait
            }
            queue.offer(item);
            lock.notifyAll();    // Wake consumers
        }
    }

    public int consume() throws InterruptedException {
        synchronized (lock) {
            while (queue.isEmpty()) {
                lock.wait();     // Release lock and wait
            }
            int val = queue.poll();
            lock.notifyAll();    // Wake producers
            return val;
        }
    }
}
```

### Critical Rules for wait/notify
1. Always call `wait()` inside `synchronized` block
2. Always use `while` loop (not `if`) — spurious wakeups
3. Prefer `notifyAll()` over `notify()` unless exactly one waiter
4. `wait()` releases the monitor lock; re-acquires on wakeup

### Complexity
- Time: O(1) per put/take
- Space: O(capacity)

---

## 9. Traffic Light Controlled Intersection (LC 1279)

### Signal
Two roads (A, B) cross. Only one road can have green at a time. Cars arrive and call `carArrived(roadId, direction)`.

### Visualization
```
       Road A (North-South)
            │  │
    ────────┼──┼──────── Road B (East-West)
            │  │

State: currentGreen = A
  Car on A → pass immediately
  Car on B → switch light to B, then pass
```

### Template: Mutex + State

```java
class TrafficLight {
    private int currentGreen = 1;  // Road 1 starts green
    private final Object lock = new Object();

    public void carArrived(int carId, int roadId, int direction,
                           Runnable turnGreen, Runnable crossCar) {
        synchronized (lock) {
            if (currentGreen != roadId) {
                turnGreen.run();           // Switch the light
                currentGreen = roadId;
            }
            crossCar.run();                // Car crosses
        }
    }
}
```

### Key Insight
- No need for complex signaling — just **mutual exclusion** with state
- The light only switches when a car from the other road arrives
- All cars on same road pass without switching (optimization)

### Complexity
- Time: O(1) per car
- Space: O(1)

---

## 10. Web Crawler Multithreaded (LC 1242)

### Signal
Given a start URL, crawl all URLs on the same hostname using multiple threads. Return all visited URLs.

### Visualization
```
                    startUrl
                   /   |    \
              url1   url2   url3    ← BFS level 1 (parallel)
             /  \      |
          url4  url5  url6          ← BFS level 2 (parallel)

ConcurrentHashMap: {url → visited}
ExecutorService: thread pool for parallel fetching
```

### Template: ConcurrentHashMap + CountDownLatch

```java
class Solution {
    public List<String> crawl(String startUrl, HtmlParser htmlParser) {
        String hostname = getHostname(startUrl);
        Set<String> visited = ConcurrentHashMap.newKeySet();
        visited.add(startUrl);

        // Use a thread pool
        ExecutorService executor = Executors.newFixedThreadPool(
            Runtime.getRuntime().availableProcessors());

        // BFS with parallel expansion
        List<String> currentLevel = new ArrayList<>();
        currentLevel.add(startUrl);

        while (!currentLevel.isEmpty()) {
            List<Future<List<String>>> futures = new ArrayList<>();

            for (String url : currentLevel) {
                futures.add(executor.submit(() -> htmlParser.getUrls(url)));
            }

            List<String> nextLevel = new ArrayList<>();
            for (Future<List<String>> future : futures) {
                try {
                    for (String url : future.get()) {
                        if (getHostname(url).equals(hostname) && visited.add(url)) {
                            nextLevel.add(url);
                        }
                    }
                } catch (Exception e) {}
            }
            currentLevel = nextLevel;
        }

        executor.shutdown();
        return new ArrayList<>(visited);
    }

    private String getHostname(String url) {
        // "http://news.example.com/page" → "news.example.com"
        String[] parts = url.split("/");
        return parts[2];
    }
}
```

### Template B: True Concurrent BFS with AtomicInteger tracking

```java
class Solution {
    private Set<String> visited = ConcurrentHashMap.newKeySet();
    private String hostname;
    private HtmlParser parser;
    private BlockingQueue<String> queue = new LinkedBlockingQueue<>();
    private AtomicInteger activeCount = new AtomicInteger(0);

    public List<String> crawl(String startUrl, HtmlParser htmlParser) {
        hostname = getHostname(startUrl);
        parser = htmlParser;
        visited.add(startUrl);
        queue.offer(startUrl);
        activeCount.set(1);

        int nThreads = 4;
        Thread[] threads = new Thread[nThreads];
        for (int i = 0; i < nThreads; i++) {
            threads[i] = new Thread(this::worker);
            threads[i].start();
        }
        for (Thread t : threads) {
            try { t.join(); } catch (InterruptedException e) {}
        }
        return new ArrayList<>(visited);
    }

    private void worker() {
        while (true) {
            String url = queue.poll();
            if (url == null) {
                if (activeCount.get() == 0) return;  // All done
                try { Thread.sleep(10); } catch (InterruptedException e) {}
                continue;
            }
            List<String> urls = parser.getUrls(url);
            for (String next : urls) {
                if (getHostname(next).equals(hostname) && visited.add(next)) {
                    activeCount.incrementAndGet();
                    queue.offer(next);
                }
            }
            activeCount.decrementAndGet();
        }
    }
}
```

### Complexity
- Time: O(V + E) / numThreads (ideally)
- Space: O(V) for visited set

---

## 11. Fizz Buzz Multithreaded (LC 1195)

### Signal
Four threads: one prints numbers, one prints "fizz", one prints "buzz", one prints "fizzbuzz". Must print 1 to n in order.

### Visualization
```
n = 15:
Thread:    num  num  fizz num  buzz fizz num  num  fizz buzz num  fizz num  num  fizzbuzz
Output:    1    2    fizz 4    buzz fizz 7    8    fizz buzz 11   fizz 13   14   fizzbuzz
```

### Template: Synchronized + State

```java
class FizzBuzz {
    private int n;
    private int current = 1;
    private final Object lock = new Object();

    public FizzBuzz(int n) { this.n = n; }

    public void fizz(Runnable printFizz) throws InterruptedException {
        synchronized (lock) {
            while (current <= n) {
                if (current % 3 == 0 && current % 5 != 0) {
                    printFizz.run();
                    current++;
                    lock.notifyAll();
                } else {
                    lock.wait();
                }
            }
        }
    }

    public void buzz(Runnable printBuzz) throws InterruptedException {
        synchronized (lock) {
            while (current <= n) {
                if (current % 5 == 0 && current % 3 != 0) {
                    printBuzz.run();
                    current++;
                    lock.notifyAll();
                } else {
                    lock.wait();
                }
            }
        }
    }

    public void fizzbuzz(Runnable printFizzBuzz) throws InterruptedException {
        synchronized (lock) {
            while (current <= n) {
                if (current % 15 == 0) {
                    printFizzBuzz.run();
                    current++;
                    lock.notifyAll();
                } else {
                    lock.wait();
                }
            }
        }
    }

    public void number(IntConsumer printNumber) throws InterruptedException {
        synchronized (lock) {
            while (current <= n) {
                if (current % 3 != 0 && current % 5 != 0) {
                    printNumber.accept(current);
                    current++;
                    lock.notifyAll();
                } else {
                    lock.wait();
                }
            }
        }
    }
}
```

### Template B: Semaphore-based (more efficient wakeup)

```java
class FizzBuzz {
    private int n;
    private AtomicInteger current = new AtomicInteger(1);
    private Semaphore fizzSem = new Semaphore(0);
    private Semaphore buzzSem = new Semaphore(0);
    private Semaphore fizzBuzzSem = new Semaphore(0);
    private Semaphore numSem = new Semaphore(1);  // Start with number

    public void fizz(Runnable printFizz) throws InterruptedException {
        while (true) {
            fizzSem.acquire();
            if (current.get() > n) return;
            printFizz.run();
            releaseNext();
        }
    }
    // Similar for buzz, fizzbuzz...

    public void number(IntConsumer printNumber) throws InterruptedException {
        while (true) {
            numSem.acquire();
            if (current.get() > n) return;
            printNumber.accept(current.get());
            releaseNext();
        }
    }

    private void releaseNext() {
        int next = current.incrementAndGet();
        if (next > n) { /* release all to exit */ fizzSem.release(); buzzSem.release(); fizzBuzzSem.release(); numSem.release(); return; }
        if (next % 15 == 0) fizzBuzzSem.release();
        else if (next % 3 == 0) fizzSem.release();
        else if (next % 5 == 0) buzzSem.release();
        else numSem.release();
    }
}
```

### Complexity
- Time: O(n) total
- Space: O(1)

---

## Common Pitfalls

### Deadlock
```
Conditions: (ALL must hold simultaneously)
1. Mutual exclusion — resource held exclusively
2. Hold and wait — hold one, wait for another
3. No preemption — cannot force release
4. Circular wait — A→B→C→A

Prevention: Break ANY one condition
- Resource ordering (breaks circular wait) ← most common in interviews
- Timeout with tryLock (breaks hold-and-wait)
- Lock-free algorithms (breaks mutual exclusion)
```

### Livelock
```
Threads keep changing state in response to each other but make no progress.
Example: Two people in hallway keep dodging the same direction.
Fix: Add randomized backoff.
```

### Starvation
```
A thread never gets access due to scheduling unfairness.
Example: Reader-preference RWLock starves writers.
Fix: Fair locks, FIFO ordering, aging.
```

### Race Conditions
```java
// BROKEN: check-then-act is not atomic
if (!map.containsKey(key)) {   // Thread A checks
    map.put(key, value);        // Thread B may insert between check and put
}

// FIX: Use atomic operations
map.putIfAbsent(key, value);

// Or: Use ConcurrentHashMap.computeIfAbsent
map.computeIfAbsent(key, k -> computeValue(k));
```

### Spurious Wakeups
```java
// WRONG
if (condition) wait();

// CORRECT — always loop
while (condition) wait();
```

---

## Thread Safety Patterns

### 1. Immutability
```java
// Immutable objects are inherently thread-safe
final class Point {
    private final int x, y;
    public Point(int x, int y) { this.x = x; this.y = y; }
}
```

### 2. Thread Confinement
```java
// Each thread has its own copy — no sharing
ThreadLocal<SimpleDateFormat> formatter =
    ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd"));
```

### 3. Lock Splitting
```java
// Instead of one lock for entire object, use fine-grained locks
private final Object readLock = new Object();
private final Object writeLock = new Object();
```

### 4. Copy-on-Write
```java
// CopyOnWriteArrayList: reads without lock, writes copy entire array
// Good when reads >> writes
List<String> listeners = new CopyOnWriteArrayList<>();
```

### 5. Compare-and-Swap (Lock-free)
```java
AtomicInteger counter = new AtomicInteger(0);
// Atomically: if current==expected, set to new value
counter.compareAndSet(expected, newValue);
// Common pattern: retry loop
int prev;
do {
    prev = counter.get();
} while (!counter.compareAndSet(prev, prev + 1));
```

---

## Summary Table

| Problem               | Core Primitive         | Pattern                     |
|-----------------------|------------------------|-----------------------------|
| Print in Order        | CountDownLatch/Sem     | Sequential signaling        |
| FooBar Alternately    | Semaphore pair         | Ping-pong                   |
| Zero Even Odd         | 3 Semaphores           | Dispatcher + workers        |
| Building H2O          | Sem + CyclicBarrier    | Ratio control + barrier     |
| Dining Philosophers   | ReentrantLock[]        | Resource ordering           |
| Bounded Queue         | Lock + 2 Conditions    | Dual-condition blocking     |
| Read-Write Lock       | Lock + 2 Conditions    | Reader count + writer flag  |
| Producer-Consumer     | BlockingQueue          | Decoupled buffer            |
| Traffic Light         | synchronized + state   | Mutex with state machine    |
| Web Crawler MT        | ConcurrentHashMap + ES | Parallel BFS                |
| FizzBuzz MT           | synchronized/Semaphore | Conditional dispatch        |
