# Classic Concurrency Problems — Java Implementations

These are the most frequently asked multithreading problems in LLD interviews. Every solution here is complete, compilable, and runnable independently.

---

## 1. Producer-Consumer Problem

### Using wait()/notify()

```java
import java.util.LinkedList;
import java.util.Queue;

public class ProducerConsumerWaitNotify {

    private static final int BUFFER_SIZE = 5;
    private final Queue<Integer> buffer = new LinkedList<>();
    private final Object lock = new Object();

    class Producer implements Runnable {
        @Override
        public void run() {
            int value = 0;
            while (true) {
                synchronized (lock) {
                    // WHY while AND NOT if:
                    // After being notified, another thread might have already
                    // filled the buffer (spurious wakeup or race with another producer).
                    // We MUST re-check the condition.
                    while (buffer.size() == BUFFER_SIZE) {
                        try {
                            System.out.println("Buffer full. Producer waiting...");
                            lock.wait();
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            return;
                        }
                    }
                    buffer.add(value);
                    System.out.println("Produced: " + value);
                    value++;
                    lock.notifyAll(); // Wake up consumers
                }
                try { Thread.sleep(100); } catch (InterruptedException e) { return; }
            }
        }
    }

    class Consumer implements Runnable {
        @Override
        public void run() {
            while (true) {
                synchronized (lock) {
                    while (buffer.isEmpty()) {
                        try {
                            System.out.println("Buffer empty. Consumer waiting...");
                            lock.wait();
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            return;
                        }
                    }
                    int value = buffer.poll();
                    System.out.println("Consumed: " + value);
                    lock.notifyAll(); // Wake up producers
                }
                try { Thread.sleep(150); } catch (InterruptedException e) { return; }
            }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ProducerConsumerWaitNotify pc = new ProducerConsumerWaitNotify();

        Thread p1 = new Thread(pc.new Producer(), "Producer-1");
        Thread p2 = new Thread(pc.new Producer(), "Producer-2");
        Thread c1 = new Thread(pc.new Consumer(), "Consumer-1");
        Thread c2 = new Thread(pc.new Consumer(), "Consumer-2");

        p1.start(); p2.start(); c1.start(); c2.start();

        Thread.sleep(3000);
        p1.interrupt(); p2.interrupt(); c1.interrupt(); c2.interrupt();
    }
}
```

**Key point — why `while` not `if`:**
- Spurious wakeups: JVM may wake a thread without `notify()` being called.
- Stolen notifications: Another thread might act on the notification first.
- Always re-check the condition after waking up.

---

### Using BlockingQueue

```java
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

public class ProducerConsumerBlockingQueue {

    private static final int BUFFER_SIZE = 5;
    private static final int POISON_PILL = -1; // Signals shutdown

    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(BUFFER_SIZE);

        // Producer
        Thread producer = new Thread(() -> {
            try {
                for (int i = 0; i < 20; i++) {
                    queue.put(i); // Blocks if queue is full
                    System.out.println("Produced: " + i);
                    Thread.sleep(50);
                }
                queue.put(POISON_PILL); // Signal consumer to stop
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        // Consumer
        Thread consumer = new Thread(() -> {
            try {
                while (true) {
                    int value = queue.take(); // Blocks if queue is empty
                    if (value == POISON_PILL) {
                        System.out.println("Consumer received poison pill. Shutting down.");
                        break;
                    }
                    System.out.println("Consumed: " + value);
                    Thread.sleep(100);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();
        System.out.println("Done.");
    }
}
```

**Poison pill pattern:** A special sentinel value placed in the queue to signal consumers that no more items will be produced. Each consumer passes the pill along if there are multiple consumers.

---

### Using Lock + Condition

```java
import java.util.LinkedList;
import java.util.Queue;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class ProducerConsumerLockCondition {

    private static final int BUFFER_SIZE = 5;
    private final Queue<Integer> buffer = new LinkedList<>();
    private final Lock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();  // Producers wait here
    private final Condition notEmpty = lock.newCondition(); // Consumers wait here

    public void produce(int value) throws InterruptedException {
        lock.lock();
        try {
            while (buffer.size() == BUFFER_SIZE) {
                notFull.await(); // Only producers wait on this condition
            }
            buffer.add(value);
            System.out.println(Thread.currentThread().getName() + " produced: " + value);
            notEmpty.signal(); // Wake one consumer specifically
        } finally {
            lock.unlock();
        }
    }

    public int consume() throws InterruptedException {
        lock.lock();
        try {
            while (buffer.isEmpty()) {
                notEmpty.await(); // Only consumers wait on this condition
            }
            int value = buffer.poll();
            System.out.println(Thread.currentThread().getName() + " consumed: " + value);
            notFull.signal(); // Wake one producer specifically
            return value;
        } finally {
            lock.unlock();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ProducerConsumerLockCondition pc = new ProducerConsumerLockCondition();

        Thread producer = new Thread(() -> {
            for (int i = 0; i < 15; i++) {
                try {
                    pc.produce(i);
                    Thread.sleep(50);
                } catch (InterruptedException e) { return; }
            }
        }, "Producer");

        Thread consumer = new Thread(() -> {
            for (int i = 0; i < 15; i++) {
                try {
                    pc.consume();
                    Thread.sleep(100);
                } catch (InterruptedException e) { return; }
            }
        }, "Consumer");

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();
    }
}
```

**Advantage over wait/notify:** Separate conditions (`notFull`, `notEmpty`) mean we only wake the right type of thread. With `notifyAll()`, ALL waiting threads wake up and re-check.

---

## 2. Reader-Writer Problem

### Problem Statement

- Multiple readers can read concurrently (no data corruption since reads don't modify).
- Writers need exclusive access (no other readers or writers).
- No reader should be blocked if no writer is active (maximize read throughput).

---

### Using ReadWriteLock

```java
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class ThreadSafeCache<K, V> {

    private final Map<K, V> cache = new HashMap<>();
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();

    public V get(K key) {
        rwLock.readLock().lock(); // Multiple threads can hold this simultaneously
        try {
            System.out.println(Thread.currentThread().getName() + " reading key: " + key);
            return cache.get(key);
        } finally {
            rwLock.readLock().unlock();
        }
    }

    public void put(K key, V value) {
        rwLock.writeLock().lock(); // Exclusive — blocks all readers and writers
        try {
            System.out.println(Thread.currentThread().getName() + " writing key: " + key);
            cache.put(key, value);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public void remove(K key) {
        rwLock.writeLock().lock();
        try {
            cache.remove(key);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ThreadSafeCache<String, String> cache = new ThreadSafeCache<>();
        cache.put("name", "Alice");

        // Multiple concurrent readers
        Runnable reader = () -> {
            for (int i = 0; i < 5; i++) {
                System.out.println(Thread.currentThread().getName() + " got: " + cache.get("name"));
                try { Thread.sleep(50); } catch (InterruptedException e) { return; }
            }
        };

        // One writer updating
        Runnable writer = () -> {
            String[] names = {"Bob", "Charlie", "Dave"};
            for (String name : names) {
                cache.put("name", name);
                try { Thread.sleep(200); } catch (InterruptedException e) { return; }
            }
        };

        Thread r1 = new Thread(reader, "Reader-1");
        Thread r2 = new Thread(reader, "Reader-2");
        Thread r3 = new Thread(reader, "Reader-3");
        Thread w1 = new Thread(writer, "Writer-1");

        r1.start(); r2.start(); r3.start(); w1.start();
        r1.join(); r2.join(); r3.join(); w1.join();
    }
}
```

---

### Using StampedLock (Java 8+)

```java
import java.util.concurrent.locks.StampedLock;

public class PointWithStampedLock {

    private double x, y;
    private final StampedLock lock = new StampedLock();

    public void move(double deltaX, double deltaY) {
        long stamp = lock.writeLock(); // Exclusive write lock
        try {
            x += deltaX;
            y += deltaY;
            System.out.println(Thread.currentThread().getName() +
                " moved to (" + x + ", " + y + ")");
        } finally {
            lock.unlockWrite(stamp);
        }
    }

    // Optimistic read — no actual locking, extremely fast
    public double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead(); // Non-blocking!
        double currentX = x;
        double currentY = y;

        // Validate: did any writer acquire the lock between our read?
        if (!lock.validate(stamp)) {
            // Fallback to full read lock
            stamp = lock.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }
        return Math.sqrt(currentX * currentX + currentY * currentY);
    }

    // Lock upgrading: read -> write
    public void moveIfAt(double expectedX, double expectedY, double newX, double newY) {
        long stamp = lock.readLock();
        try {
            while (x == expectedX && y == expectedY) {
                // Try to upgrade to write lock
                long writeStamp = lock.tryConvertToWriteLock(stamp);
                if (writeStamp != 0L) {
                    // Upgrade successful
                    stamp = writeStamp;
                    x = newX;
                    y = newY;
                    break;
                } else {
                    // Upgrade failed, release read lock and acquire write lock
                    lock.unlockRead(stamp);
                    stamp = lock.writeLock();
                }
            }
        } finally {
            lock.unlock(stamp);
        }
    }

    public static void main(String[] args) throws InterruptedException {
        PointWithStampedLock point = new PointWithStampedLock();

        Thread writer = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                point.move(1, 1);
                try { Thread.sleep(100); } catch (InterruptedException e) { return; }
            }
        }, "Writer");

        Thread reader = new Thread(() -> {
            for (int i = 0; i < 20; i++) {
                System.out.println("Distance: " + point.distanceFromOrigin());
                try { Thread.sleep(50); } catch (InterruptedException e) { return; }
            }
        }, "Reader");

        writer.start();
        reader.start();
        writer.join();
        reader.join();
    }
}
```

---

### Custom Reader-Writer using synchronized

```java
public class CustomReadWriteLock {

    private int readers = 0;
    private boolean writerActive = false;
    private int writersWaiting = 0;

    public synchronized void acquireReadLock() throws InterruptedException {
        // Don't let readers in if a writer is waiting (prevents writer starvation)
        while (writerActive || writersWaiting > 0) {
            wait();
        }
        readers++;
    }

    public synchronized void releaseReadLock() {
        readers--;
        if (readers == 0) {
            notifyAll(); // Wake waiting writers
        }
    }

    public synchronized void acquireWriteLock() throws InterruptedException {
        writersWaiting++;
        while (readers > 0 || writerActive) {
            wait();
        }
        writersWaiting--;
        writerActive = true;
    }

    public synchronized void releaseWriteLock() {
        writerActive = false;
        notifyAll(); // Wake waiting readers and writers
    }

    public static void main(String[] args) throws InterruptedException {
        CustomReadWriteLock rwLock = new CustomReadWriteLock();
        int[] sharedData = {0};

        Runnable reader = () -> {
            for (int i = 0; i < 5; i++) {
                try {
                    rwLock.acquireReadLock();
                    System.out.println(Thread.currentThread().getName() +
                        " reading: " + sharedData[0]);
                    Thread.sleep(50);
                    rwLock.releaseReadLock();
                } catch (InterruptedException e) { return; }
            }
        };

        Runnable writer = () -> {
            for (int i = 0; i < 3; i++) {
                try {
                    rwLock.acquireWriteLock();
                    sharedData[0]++;
                    System.out.println(Thread.currentThread().getName() +
                        " wrote: " + sharedData[0]);
                    Thread.sleep(100);
                    rwLock.releaseWriteLock();
                } catch (InterruptedException e) { return; }
            }
        };

        Thread r1 = new Thread(reader, "Reader-1");
        Thread r2 = new Thread(reader, "Reader-2");
        Thread w1 = new Thread(writer, "Writer-1");

        r1.start(); r2.start(); w1.start();
        r1.join(); r2.join(); w1.join();
    }
}
```

---

## 3. Dining Philosophers Problem

### Problem Statement

5 philosophers sit at a round table. Between each pair is one fork (5 forks total). A philosopher needs both adjacent forks to eat. If all 5 pick up their left fork simultaneously, deadlock occurs (each holds one fork, waiting for the other).

---

### Solution 1: Resource Ordering

Pick up the lower-numbered fork first. This breaks the circular wait condition.

```java
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class DiningPhilosophersOrdering {

    private static final int NUM_PHILOSOPHERS = 5;
    private static final Lock[] forks = new Lock[NUM_PHILOSOPHERS];

    static {
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            forks[i] = new ReentrantLock();
        }
    }

    static class Philosopher implements Runnable {
        private final int id;

        Philosopher(int id) { this.id = id; }

        @Override
        public void run() {
            try {
                for (int i = 0; i < 3; i++) {
                    think();
                    eat();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            System.out.println("Philosopher " + id + " finished.");
        }

        private void think() throws InterruptedException {
            System.out.println("Philosopher " + id + " is thinking.");
            Thread.sleep((long) (Math.random() * 200));
        }

        private void eat() throws InterruptedException {
            int leftFork = id;
            int rightFork = (id + 1) % NUM_PHILOSOPHERS;

            // Always pick up the lower-numbered fork first
            int first = Math.min(leftFork, rightFork);
            int second = Math.max(leftFork, rightFork);

            forks[first].lock();
            forks[second].lock();
            try {
                System.out.println("Philosopher " + id + " is eating.");
                Thread.sleep((long) (Math.random() * 200));
            } finally {
                forks[second].unlock();
                forks[first].unlock();
            }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Thread[] threads = new Thread[NUM_PHILOSOPHERS];
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            threads[i] = new Thread(new Philosopher(i), "Phil-" + i);
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("All philosophers done.");
    }
}
```

---

### Solution 2: Using Semaphore (limit to 4 concurrent eaters)

```java
import java.util.concurrent.Semaphore;

public class DiningPhilosophersSemaphore {

    private static final int NUM_PHILOSOPHERS = 5;
    private static final Semaphore[] forks = new Semaphore[NUM_PHILOSOPHERS];
    // Allow at most 4 philosophers to attempt eating — prevents deadlock
    private static final Semaphore diningPermit = new Semaphore(NUM_PHILOSOPHERS - 1);

    static {
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            forks[i] = new Semaphore(1);
        }
    }

    static class Philosopher implements Runnable {
        private final int id;

        Philosopher(int id) { this.id = id; }

        @Override
        public void run() {
            try {
                for (int i = 0; i < 3; i++) {
                    think();
                    eat();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        private void think() throws InterruptedException {
            System.out.println("Philosopher " + id + " thinking.");
            Thread.sleep((long) (Math.random() * 200));
        }

        private void eat() throws InterruptedException {
            diningPermit.acquire(); // At most 4 can try
            forks[id].acquire();                      // Left fork
            forks[(id + 1) % NUM_PHILOSOPHERS].acquire(); // Right fork

            System.out.println("Philosopher " + id + " eating.");
            Thread.sleep((long) (Math.random() * 200));

            forks[(id + 1) % NUM_PHILOSOPHERS].release();
            forks[id].release();
            diningPermit.release();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Thread[] threads = new Thread[NUM_PHILOSOPHERS];
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            threads[i] = new Thread(new Philosopher(i));
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("All philosophers done.");
    }
}
```

---

### Solution 3: Using tryLock with Timeout

```java
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class DiningPhilosophersTryLock {

    private static final int NUM_PHILOSOPHERS = 5;
    private static final Lock[] forks = new Lock[NUM_PHILOSOPHERS];

    static {
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            forks[i] = new ReentrantLock();
        }
    }

    static class Philosopher implements Runnable {
        private final int id;

        Philosopher(int id) { this.id = id; }

        @Override
        public void run() {
            try {
                for (int i = 0; i < 3; i++) {
                    think();
                    while (!tryEat()) {
                        // Back off and try again
                        Thread.sleep((long) (Math.random() * 50));
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        private void think() throws InterruptedException {
            System.out.println("Philosopher " + id + " thinking.");
            Thread.sleep((long) (Math.random() * 200));
        }

        private boolean tryEat() throws InterruptedException {
            Lock leftFork = forks[id];
            Lock rightFork = forks[(id + 1) % NUM_PHILOSOPHERS];

            if (leftFork.tryLock(100, TimeUnit.MILLISECONDS)) {
                try {
                    if (rightFork.tryLock(100, TimeUnit.MILLISECONDS)) {
                        try {
                            System.out.println("Philosopher " + id + " eating.");
                            Thread.sleep((long) (Math.random() * 200));
                            return true;
                        } finally {
                            rightFork.unlock();
                        }
                    }
                } finally {
                    leftFork.unlock(); // Release left if couldn't get right
                }
            }
            return false; // Couldn't get both forks, will retry
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Thread[] threads = new Thread[NUM_PHILOSOPHERS];
        for (int i = 0; i < NUM_PHILOSOPHERS; i++) {
            threads[i] = new Thread(new Philosopher(i));
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("All philosophers done.");
    }
}
```

---

## 4. Thread-Safe Singleton Patterns

### All Five Patterns

```java
// ===== 1. Eager Initialization =====
class EagerSingleton {
    // Instance created at class loading time — guaranteed thread-safe by JVM
    private static final EagerSingleton INSTANCE = new EagerSingleton();

    private EagerSingleton() {}

    public static EagerSingleton getInstance() {
        return INSTANCE;
    }
}

// ===== 2. Lazy with synchronized method =====
class SynchronizedSingleton {
    private static SynchronizedSingleton instance;

    private SynchronizedSingleton() {}

    // Every call pays synchronization cost — even after instance is created
    public static synchronized SynchronizedSingleton getInstance() {
        if (instance == null) {
            instance = new SynchronizedSingleton();
        }
        return instance;
    }
}

// ===== 3. Double-Checked Locking with volatile =====
class DCLSingleton {
    // volatile prevents instruction reordering
    // Without it, a partially constructed object might be visible to other threads
    private static volatile DCLSingleton instance;

    private DCLSingleton() {}

    public static DCLSingleton getInstance() {
        if (instance == null) {            // First check (no locking)
            synchronized (DCLSingleton.class) {
                if (instance == null) {    // Second check (with lock)
                    instance = new DCLSingleton();
                }
            }
        }
        return instance;
    }
}

// ===== 4. Bill Pugh — Static Inner Class Holder =====
class BillPughSingleton {
    private BillPughSingleton() {}

    // Inner class is not loaded until getInstance() is called
    // Class loading is guaranteed thread-safe by JVM
    private static class Holder {
        private static final BillPughSingleton INSTANCE = new BillPughSingleton();
    }

    public static BillPughSingleton getInstance() {
        return Holder.INSTANCE;
    }
}

// ===== 5. Enum Singleton =====
enum EnumSingleton {
    INSTANCE;

    // Enum guarantees: thread-safe, serialization-safe, reflection-safe
    public void doSomething() {
        System.out.println("Enum singleton working.");
    }
}

// ===== Test =====
public class SingletonDemo {
    public static void main(String[] args) {
        // Verify all patterns return same instance across threads
        Runnable testDCL = () -> {
            DCLSingleton s = DCLSingleton.getInstance();
            System.out.println(Thread.currentThread().getName() + ": " + s.hashCode());
        };

        for (int i = 0; i < 5; i++) {
            new Thread(testDCL, "T-" + i).start();
        }
    }
}
```

### Trade-offs Table

| Pattern | Lazy? | Thread-Safe? | Reflection-Safe? | Serialization-Safe? | Performance |
|---------|-------|-------------|-----------------|--------------------:|-------------|
| Eager | No | Yes (JVM) | No | No | Best |
| Synchronized | Yes | Yes | No | No | Worst |
| DCL + volatile | Yes | Yes | No | No | Good |
| Bill Pugh | Yes | Yes (JVM) | No | No | Best |
| Enum | No | Yes (JVM) | Yes | Yes | Best |

---

## 5. CountDownLatch Problems

### Scenario: Wait for N Services to Start

```java
import java.util.concurrent.CountDownLatch;

public class ServiceStartup {

    public static void main(String[] args) throws InterruptedException {
        int serviceCount = 3;
        CountDownLatch latch = new CountDownLatch(serviceCount);

        // Simulate services starting
        new Thread(() -> startService("Database", 2000, latch)).start();
        new Thread(() -> startService("Cache", 1000, latch)).start();
        new Thread(() -> startService("MessageQueue", 1500, latch)).start();

        System.out.println("Main thread waiting for all services...");
        latch.await(); // Blocks until count reaches 0
        System.out.println("All services started! Application ready.");
    }

    static void startService(String name, long timeMs, CountDownLatch latch) {
        try {
            System.out.println(name + " starting...");
            Thread.sleep(timeMs); // Simulate startup time
            System.out.println(name + " started!");
            latch.countDown(); // Decrement count
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

---

### Scenario: Race Simulation (Starting Gun)

```java
import java.util.concurrent.CountDownLatch;

public class RaceSimulation {

    public static void main(String[] args) throws InterruptedException {
        int numRunners = 5;
        CountDownLatch startGun = new CountDownLatch(1);    // One signal starts all
        CountDownLatch finishLine = new CountDownLatch(numRunners); // Wait for all to finish

        for (int i = 1; i <= numRunners; i++) {
            final int runnerId = i;
            new Thread(() -> {
                try {
                    System.out.println("Runner " + runnerId + " ready at the line.");
                    startGun.await(); // All runners wait here
                    // Race!
                    long raceTime = (long) (Math.random() * 3000);
                    Thread.sleep(raceTime);
                    System.out.println("Runner " + runnerId + " finished in " + raceTime + "ms!");
                    finishLine.countDown();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }).start();
        }

        Thread.sleep(1000); // Dramatic pause
        System.out.println("GO!");
        startGun.countDown(); // Release all runners

        finishLine.await();
        System.out.println("Race complete!");
    }
}
```

---

## 6. CyclicBarrier Problems

### Scenario: Parallel Matrix Computation

```java
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CyclicBarrier;

public class ParallelMatrixComputation {

    private static final int NUM_WORKERS = 3;
    private static final int NUM_PHASES = 3;
    private static final int[] results = new int[NUM_WORKERS];

    public static void main(String[] args) throws InterruptedException {
        // Barrier action: runs when all threads arrive
        CyclicBarrier barrier = new CyclicBarrier(NUM_WORKERS, () -> {
            int sum = 0;
            for (int r : results) sum += r;
            System.out.println("--- Phase complete. Combined result: " + sum + " ---");
        });

        for (int i = 0; i < NUM_WORKERS; i++) {
            final int workerId = i;
            new Thread(() -> {
                try {
                    for (int phase = 0; phase < NUM_PHASES; phase++) {
                        // Compute this phase
                        int computed = (workerId + 1) * (phase + 1) * 10;
                        results[workerId] = computed;
                        System.out.println("Worker " + workerId +
                            " computed " + computed + " in phase " + phase);

                        barrier.await(); // Wait for all workers to finish this phase
                        // CyclicBarrier resets — can be used again for next phase
                    }
                } catch (InterruptedException | BrokenBarrierException e) {
                    Thread.currentThread().interrupt();
                }
            }, "Worker-" + i).start();
        }

        Thread.sleep(3000); // Wait for completion
    }
}
```

### CyclicBarrier vs CountDownLatch

| Feature | CyclicBarrier | CountDownLatch |
|---------|--------------|----------------|
| Reusable? | Yes (resets after each trip) | No (one-shot) |
| Who waits? | Threads wait for each other | Threads wait for events |
| Reset | Automatic after all arrive | Cannot reset |
| Action | Optional barrier action | No built-in action |
| Use case | Phased computation | Service startup, race start |

---

## 7. Semaphore Problems

### Connection Pool

```java
import java.util.concurrent.Semaphore;
import java.util.concurrent.ConcurrentLinkedQueue;

public class ConnectionPool {

    private final Semaphore semaphore;
    private final ConcurrentLinkedQueue<Connection> pool;

    public ConnectionPool(int maxConnections) {
        this.semaphore = new Semaphore(maxConnections, true); // fair
        this.pool = new ConcurrentLinkedQueue<>();
        for (int i = 0; i < maxConnections; i++) {
            pool.add(new Connection(i));
        }
    }

    public Connection acquire() throws InterruptedException {
        semaphore.acquire(); // Block if no connections available
        return pool.poll();
    }

    public void release(Connection conn) {
        pool.offer(conn);
        semaphore.release(); // Signal that a connection is available
    }

    static class Connection {
        private final int id;
        Connection(int id) { this.id = id; }
        public void execute(String query) {
            System.out.println(Thread.currentThread().getName() +
                " [Conn-" + id + "] executing: " + query);
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ConnectionPool pool = new ConnectionPool(3); // Only 3 connections

        // 10 threads competing for 3 connections
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            final int taskId = i;
            threads[i] = new Thread(() -> {
                try {
                    Connection conn = pool.acquire();
                    conn.execute("SELECT * FROM table_" + taskId);
                    Thread.sleep(200); // Simulate query time
                    pool.release(conn);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "Worker-" + i);
            threads[i].start();
        }

        for (Thread t : threads) t.join();
        System.out.println("All queries complete.");
    }
}
```

---

### Rate Limiter (Token Bucket)

```java
import java.util.concurrent.Semaphore;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class TokenBucketRateLimiter {

    private final Semaphore tokens;
    private final int maxTokens;
    private final ScheduledExecutorService refiller;

    public TokenBucketRateLimiter(int maxTokens, int refillRate, TimeUnit unit) {
        this.maxTokens = maxTokens;
        this.tokens = new Semaphore(maxTokens);
        this.refiller = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "token-refiller");
            t.setDaemon(true);
            return t;
        });

        // Periodically add tokens back
        refiller.scheduleAtFixedRate(() -> {
            int availablePermits = tokens.availablePermits();
            if (availablePermits < maxTokens) {
                tokens.release(Math.min(refillRate, maxTokens - availablePermits));
            }
        }, 1, 1, unit);
    }

    public boolean tryAcquire() {
        return tokens.tryAcquire();
    }

    public void acquire() throws InterruptedException {
        tokens.acquire();
    }

    public void shutdown() {
        refiller.shutdown();
    }

    public static void main(String[] args) throws InterruptedException {
        // 5 tokens max, refill 2 per second
        TokenBucketRateLimiter limiter = new TokenBucketRateLimiter(5, 2, TimeUnit.SECONDS);

        // Burst: consume all 5 tokens quickly
        for (int i = 0; i < 8; i++) {
            if (limiter.tryAcquire()) {
                System.out.println("Request " + i + " ALLOWED at " + System.currentTimeMillis());
            } else {
                System.out.println("Request " + i + " REJECTED at " + System.currentTimeMillis());
            }
            Thread.sleep(100);
        }

        // Wait for refill
        System.out.println("Waiting for token refill...");
        Thread.sleep(2000);

        for (int i = 8; i < 12; i++) {
            if (limiter.tryAcquire()) {
                System.out.println("Request " + i + " ALLOWED at " + System.currentTimeMillis());
            } else {
                System.out.println("Request " + i + " REJECTED at " + System.currentTimeMillis());
            }
            Thread.sleep(100);
        }

        limiter.shutdown();
    }
}
```

---

## 8. Exchanger Problem

### Double-Buffering with Exchanger

```java
import java.util.concurrent.Exchanger;
import java.util.ArrayList;
import java.util.List;

public class ExchangerDemo {

    private static final int BUFFER_SIZE = 5;

    public static void main(String[] args) throws InterruptedException {
        Exchanger<List<Integer>> exchanger = new Exchanger<>();

        // Producer fills a buffer, then exchanges it with consumer's empty buffer
        Thread producer = new Thread(() -> {
            List<Integer> buffer = new ArrayList<>(BUFFER_SIZE);
            int value = 0;
            try {
                for (int round = 0; round < 3; round++) {
                    // Fill buffer
                    for (int i = 0; i < BUFFER_SIZE; i++) {
                        buffer.add(value++);
                    }
                    System.out.println("Producer filled: " + buffer);
                    // Exchange full buffer for empty one
                    buffer = exchanger.exchange(buffer);
                    System.out.println("Producer got back empty buffer: " + buffer);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }, "Producer");

        // Consumer gets a full buffer, processes it, then exchanges empty buffer back
        Thread consumer = new Thread(() -> {
            List<Integer> buffer = new ArrayList<>(BUFFER_SIZE);
            try {
                for (int round = 0; round < 3; round++) {
                    // Exchange empty buffer for full one
                    buffer = exchanger.exchange(buffer);
                    System.out.println("Consumer received: " + buffer);
                    // Process all items
                    for (int item : buffer) {
                        System.out.println("  Consumer processing: " + item);
                    }
                    buffer.clear(); // Empty it for exchange back
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }, "Consumer");

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();
    }
}
```

---

## 9. Phaser Problems

### Multi-Phase File Processing

```java
import java.util.concurrent.Phaser;

public class PhaserFileProcessing {

    public static void main(String[] args) throws InterruptedException {
        // 1 = registering the main thread (to control termination)
        Phaser phaser = new Phaser(1);

        String[] files = {"file1.csv", "file2.csv", "file3.csv"};

        for (String file : files) {
            phaser.register(); // Dynamically add participant
            new Thread(new FileProcessor(file, phaser), "Processor-" + file).start();
        }

        // Phase 0: Wait for all to finish reading
        int phase = phaser.arriveAndAwaitAdvance();
        System.out.println("=== All files read (phase " + (phase - 1) + " complete) ===");

        // Phase 1: Wait for all to finish processing
        phase = phaser.arriveAndAwaitAdvance();
        System.out.println("=== All files processed (phase " + (phase - 1) + " complete) ===");

        // Phase 2: Wait for all to finish writing
        phase = phaser.arriveAndAwaitAdvance();
        System.out.println("=== All files written (phase " + (phase - 1) + " complete) ===");

        phaser.arriveAndDeregister(); // Main thread done
        System.out.println("Pipeline complete.");
    }

    static class FileProcessor implements Runnable {
        private final String fileName;
        private final Phaser phaser;

        FileProcessor(String fileName, Phaser phaser) {
            this.fileName = fileName;
            this.phaser = phaser;
        }

        @Override
        public void run() {
            try {
                // Phase 0: Read file
                System.out.println(Thread.currentThread().getName() + " reading " + fileName);
                Thread.sleep((long) (Math.random() * 500));
                phaser.arriveAndAwaitAdvance();

                // Phase 1: Process data
                System.out.println(Thread.currentThread().getName() + " processing " + fileName);
                Thread.sleep((long) (Math.random() * 500));
                phaser.arriveAndAwaitAdvance();

                // Phase 2: Write results
                System.out.println(Thread.currentThread().getName() + " writing " + fileName);
                Thread.sleep((long) (Math.random() * 500));
                phaser.arriveAndDeregister(); // Done with all phases

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}
```

---

## 10. ForkJoinPool & RecursiveTask

### Parallel Merge Sort

```java
import java.util.Arrays;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.RecursiveAction;

public class ParallelMergeSort extends RecursiveAction {

    private static final int THRESHOLD = 4; // Below this, sort sequentially
    private final int[] array;
    private final int left;
    private final int right;

    public ParallelMergeSort(int[] array, int left, int right) {
        this.array = array;
        this.left = left;
        this.right = right;
    }

    @Override
    protected void compute() {
        if (right - left <= THRESHOLD) {
            // Sequential sort for small arrays
            Arrays.sort(array, left, right);
            return;
        }

        int mid = (left + right) / 2;
        ParallelMergeSort leftTask = new ParallelMergeSort(array, left, mid);
        ParallelMergeSort rightTask = new ParallelMergeSort(array, mid, right);

        // Fork both halves
        invokeAll(leftTask, rightTask);

        // Merge
        merge(array, left, mid, right);
    }

    private void merge(int[] arr, int left, int mid, int right) {
        int[] temp = Arrays.copyOfRange(arr, left, right);
        int i = 0, j = mid - left, k = left;

        while (i < mid - left && j < right - left) {
            if (temp[i] <= temp[j]) {
                arr[k++] = temp[i++];
            } else {
                arr[k++] = temp[j++];
            }
        }
        while (i < mid - left) arr[k++] = temp[i++];
        while (j < right - left) arr[k++] = temp[j++];
    }

    public static void main(String[] args) {
        int[] array = {38, 27, 43, 3, 9, 82, 10, 1, 45, 67, 23, 5};
        System.out.println("Before: " + Arrays.toString(array));

        ForkJoinPool pool = ForkJoinPool.commonPool();
        pool.invoke(new ParallelMergeSort(array, 0, array.length));

        System.out.println("After:  " + Arrays.toString(array));
    }
}
```

---

### Parallel Sum

```java
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.RecursiveTask;

public class ParallelSum extends RecursiveTask<Long> {

    private static final int THRESHOLD = 10_000;
    private final long[] array;
    private final int start;
    private final int end;

    public ParallelSum(long[] array, int start, int end) {
        this.array = array;
        this.start = start;
        this.end = end;
    }

    @Override
    protected Long compute() {
        if (end - start <= THRESHOLD) {
            // Sequential computation
            long sum = 0;
            for (int i = start; i < end; i++) {
                sum += array[i];
            }
            return sum;
        }

        int mid = (start + end) / 2;
        ParallelSum leftTask = new ParallelSum(array, start, mid);
        ParallelSum rightTask = new ParallelSum(array, mid, end);

        leftTask.fork();  // Submit to pool
        long rightResult = rightTask.compute(); // Compute right in current thread
        long leftResult = leftTask.join();      // Wait for left

        return leftResult + rightResult;
    }

    public static void main(String[] args) {
        int size = 100_000;
        long[] array = new long[size];
        for (int i = 0; i < size; i++) array[i] = i + 1;

        ForkJoinPool pool = ForkJoinPool.commonPool();
        long start = System.nanoTime();
        long result = pool.invoke(new ParallelSum(array, 0, array.length));
        long elapsed = System.nanoTime() - start;

        System.out.println("Sum: " + result);
        System.out.println("Expected: " + ((long) size * (size + 1) / 2));
        System.out.println("Time: " + elapsed / 1_000_000.0 + "ms");
        System.out.println("Parallelism: " + pool.getParallelism());
    }
}
```

### Work-Stealing Algorithm

How `ForkJoinPool` differs from `ThreadPoolExecutor`:
- Each worker thread has its **own deque** (double-ended queue) of tasks.
- When a worker's deque is empty, it **steals** from the tail of another worker's deque.
- `fork()` pushes to the head of the current worker's deque.
- `join()` can execute the task inline if it hasn't been stolen.
- Result: Better load balancing for recursive divide-and-conquer workloads.

---

## 11. Thread-Safe Data Structures from Scratch

### Thread-Safe Stack

```java
import java.util.EmptyStackException;

public class ThreadSafeStack<T> {

    private Object[] elements;
    private int top;
    private static final int DEFAULT_CAPACITY = 16;

    public ThreadSafeStack() {
        elements = new Object[DEFAULT_CAPACITY];
        top = -1;
    }

    public synchronized void push(T item) {
        if (top == elements.length - 1) {
            resize();
        }
        elements[++top] = item;
        notifyAll(); // Notify threads waiting on pop
    }

    @SuppressWarnings("unchecked")
    public synchronized T pop() {
        if (top == -1) {
            throw new EmptyStackException();
        }
        T item = (T) elements[top];
        elements[top--] = null; // Help GC
        return item;
    }

    // Blocking pop — waits until an element is available
    @SuppressWarnings("unchecked")
    public synchronized T blockingPop() throws InterruptedException {
        while (top == -1) {
            wait();
        }
        T item = (T) elements[top];
        elements[top--] = null;
        return item;
    }

    @SuppressWarnings("unchecked")
    public synchronized T peek() {
        if (top == -1) {
            throw new EmptyStackException();
        }
        return (T) elements[top];
    }

    public synchronized boolean isEmpty() {
        return top == -1;
    }

    public synchronized int size() {
        return top + 1;
    }

    private void resize() {
        Object[] newElements = new Object[elements.length * 2];
        System.arraycopy(elements, 0, newElements, 0, elements.length);
        elements = newElements;
    }

    public static void main(String[] args) throws InterruptedException {
        ThreadSafeStack<Integer> stack = new ThreadSafeStack<>();

        Thread pusher = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                stack.push(i);
                System.out.println("Pushed: " + i);
                try { Thread.sleep(50); } catch (InterruptedException e) { return; }
            }
        });

        Thread popper = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                try {
                    int val = stack.blockingPop();
                    System.out.println("Popped: " + val);
                } catch (InterruptedException e) { return; }
            }
        });

        pusher.start();
        popper.start();
        pusher.join();
        popper.join();
    }
}
```

---

### Thread-Safe Bounded Queue (Lock + Condition)

```java
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class BoundedBlockingQueue<T> {

    private final Object[] items;
    private int head, tail, count;
    private final Lock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();

    public BoundedBlockingQueue(int capacity) {
        items = new Object[capacity];
    }

    public void enqueue(T item) throws InterruptedException {
        lock.lock();
        try {
            while (count == items.length) {
                notFull.await();
            }
            items[tail] = item;
            tail = (tail + 1) % items.length;
            count++;
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
    }

    @SuppressWarnings("unchecked")
    public T dequeue() throws InterruptedException {
        lock.lock();
        try {
            while (count == 0) {
                notEmpty.await();
            }
            T item = (T) items[head];
            items[head] = null;
            head = (head + 1) % items.length;
            count--;
            notFull.signal();
            return item;
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try {
            return count;
        } finally {
            lock.unlock();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        BoundedBlockingQueue<String> queue = new BoundedBlockingQueue<>(3);

        Thread producer = new Thread(() -> {
            String[] messages = {"Hello", "World", "Foo", "Bar", "Baz", "Done"};
            for (String msg : messages) {
                try {
                    queue.enqueue(msg);
                    System.out.println("Enqueued: " + msg);
                } catch (InterruptedException e) { return; }
            }
        }, "Producer");

        Thread consumer = new Thread(() -> {
            for (int i = 0; i < 6; i++) {
                try {
                    String msg = queue.dequeue();
                    System.out.println("Dequeued: " + msg);
                    Thread.sleep(200);
                } catch (InterruptedException e) { return; }
            }
        }, "Consumer");

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();
    }
}
```

---

### Thread-Safe LRU Cache

```java
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.concurrent.locks.ReentrantLock;

public class ConcurrentLRUCache<K, V> {

    private final int capacity;
    private final ConcurrentHashMap<K, V> map;
    private final ConcurrentLinkedDeque<K> accessOrder;
    private final ReentrantLock evictionLock = new ReentrantLock();

    public ConcurrentLRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new ConcurrentHashMap<>(capacity);
        this.accessOrder = new ConcurrentLinkedDeque<>();
    }

    public V get(K key) {
        V value = map.get(key);
        if (value != null) {
            // Move to most recently used
            accessOrder.remove(key);
            accessOrder.addFirst(key);
        }
        return value;
    }

    public void put(K key, V value) {
        if (map.containsKey(key)) {
            // Update existing
            map.put(key, value);
            accessOrder.remove(key);
            accessOrder.addFirst(key);
            return;
        }

        // Evict if at capacity
        evictionLock.lock();
        try {
            while (map.size() >= capacity) {
                K evicted = accessOrder.pollLast(); // Remove least recently used
                if (evicted != null) {
                    map.remove(evicted);
                    System.out.println("Evicted: " + evicted);
                }
            }
            map.put(key, value);
            accessOrder.addFirst(key);
        } finally {
            evictionLock.unlock();
        }
    }

    public int size() {
        return map.size();
    }

    public static void main(String[] args) throws InterruptedException {
        ConcurrentLRUCache<String, Integer> cache = new ConcurrentLRUCache<>(3);

        // Single-threaded demonstration
        cache.put("a", 1);
        cache.put("b", 2);
        cache.put("c", 3);
        System.out.println("Get b: " + cache.get("b")); // b becomes most recent

        cache.put("d", 4); // Should evict "a" (least recently used)
        System.out.println("Get a: " + cache.get("a")); // null — evicted
        System.out.println("Get b: " + cache.get("b")); // 2 — still present
        System.out.println("Size: " + cache.size());

        // Multi-threaded stress test
        ConcurrentLRUCache<Integer, Integer> stressCache = new ConcurrentLRUCache<>(100);
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            final int start = i * 50;
            threads[i] = new Thread(() -> {
                for (int j = start; j < start + 50; j++) {
                    stressCache.put(j, j * 10);
                    stressCache.get(j - 5); // Random access
                }
            });
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("Stress test done. Cache size: " + stressCache.size());
    }
}
```

#### Alternative: Synchronized LinkedHashMap

```java
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

public class SynchronizedLRUCache<K, V> {

    private final Map<K, V> cache;

    public SynchronizedLRUCache(int capacity) {
        // accessOrder=true makes LinkedHashMap order by access time
        Map<K, V> lruMap = new LinkedHashMap<K, V>(capacity, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
                return size() > capacity;
            }
        };
        // Wrap in synchronized map for thread safety
        this.cache = Collections.synchronizedMap(lruMap);
    }

    public V get(K key) {
        return cache.get(key);
    }

    public void put(K key, V value) {
        cache.put(key, value);
    }

    public int size() {
        return cache.size();
    }

    public static void main(String[] args) {
        SynchronizedLRUCache<String, Integer> cache = new SynchronizedLRUCache<>(3);
        cache.put("x", 10);
        cache.put("y", 20);
        cache.put("z", 30);
        cache.get("x");       // x is now most recently used
        cache.put("w", 40);   // Evicts y (least recently used)
        System.out.println("y: " + cache.get("y")); // null
        System.out.println("x: " + cache.get("x")); // 10
    }
}
```

---

## 12. Common Concurrency Pitfalls

### Deadlock: Example + Detection + Prevention

```java
public class DeadlockExample {

    private static final Object lockA = new Object();
    private static final Object lockB = new Object();

    public static void main(String[] args) {
        // Thread 1: locks A then B
        Thread t1 = new Thread(() -> {
            synchronized (lockA) {
                System.out.println("T1 holds lockA, waiting for lockB...");
                try { Thread.sleep(100); } catch (InterruptedException e) {}
                synchronized (lockB) {
                    System.out.println("T1 holds both locks.");
                }
            }
        }, "T1");

        // Thread 2: locks B then A — DEADLOCK!
        Thread t2 = new Thread(() -> {
            synchronized (lockB) {
                System.out.println("T2 holds lockB, waiting for lockA...");
                try { Thread.sleep(100); } catch (InterruptedException e) {}
                synchronized (lockA) {
                    System.out.println("T2 holds both locks.");
                }
            }
        }, "T2");

        t1.start();
        t2.start();

        // Detection: use jstack <pid> or ThreadMXBean
        // Neither "holds both locks" will print — deadlocked.
    }
}
```

**Detection at runtime:**
```java
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

// Can be called from a monitoring thread:
ThreadMXBean bean = ManagementFactory.getThreadMXBean();
long[] deadlockedThreads = bean.findDeadlockedThreads();
if (deadlockedThreads != null) {
    System.out.println("DEADLOCK DETECTED! Thread IDs: ");
    // ...log and alert
}
```

**Prevention strategies:**
1. **Lock ordering** — always acquire locks in a consistent global order.
2. **Lock timeout** — use `tryLock(timeout)` instead of blocking forever.
3. **Avoid nested locks** — minimize the scope where multiple locks are held.
4. **Use higher-level constructs** — `java.util.concurrent` classes handle locking internally.

---

### Livelock: Example

```java
public class LivelockExample {

    static class Spoon {
        private Diner owner;
        Spoon(Diner d) { owner = d; }
        synchronized Diner getOwner() { return owner; }
        synchronized void setOwner(Diner d) { owner = d; }
        synchronized void use() {
            System.out.println(owner.name + " is eating!");
        }
    }

    static class Diner {
        String name;
        boolean isHungry;

        Diner(String name) { this.name = name; this.isHungry = true; }

        void eatWith(Spoon spoon, Diner partner) {
            while (isHungry) {
                if (spoon.getOwner() != this) {
                    try { Thread.sleep(1); } catch (InterruptedException e) { return; }
                    continue;
                }
                // Politely pass if partner is hungry — LIVELOCK!
                if (partner.isHungry) {
                    System.out.println(name + ": You eat first, " + partner.name + "!");
                    spoon.setOwner(partner);
                    continue;
                }
                // Eat
                spoon.use();
                isHungry = false;
                spoon.setOwner(partner);
            }
        }
    }

    public static void main(String[] args) {
        Diner alice = new Diner("Alice");
        Diner bob = new Diner("Bob");
        Spoon spoon = new Spoon(alice);

        // Both endlessly defer to each other — livelock
        // (add Thread.sleep or random backoff to resolve)
        new Thread(() -> alice.eatWith(spoon, bob)).start();
        new Thread(() -> bob.eatWith(spoon, alice)).start();
    }
}
```

**Fix:** Add random backoff before passing the spoon.

---

### Starvation: Example + Fairness

```java
import java.util.concurrent.locks.ReentrantLock;

public class StarvationExample {

    // Unfair lock: threads may starve if high-priority threads keep grabbing it
    private static final ReentrantLock unfairLock = new ReentrantLock(false);

    // Fair lock: FIFO ordering, prevents starvation
    private static final ReentrantLock fairLock = new ReentrantLock(true);

    public static void main(String[] args) {
        ReentrantLock lock = fairLock; // Switch to unfairLock to see starvation

        for (int i = 0; i < 5; i++) {
            final int id = i;
            new Thread(() -> {
                for (int j = 0; j < 3; j++) {
                    lock.lock();
                    try {
                        System.out.println("Thread-" + id + " acquired lock (iteration " + j + ")");
                        Thread.sleep(100);
                    } catch (InterruptedException e) {
                        return;
                    } finally {
                        lock.unlock();
                    }
                }
            }, "Thread-" + id).start();
        }
    }
}
```

With `fair=true`, threads acquire the lock in FIFO order. Without fairness, a thread that just released a lock can immediately re-acquire it, starving others.

---

### Race Condition: Check-Then-Act

```java
import java.util.concurrent.atomic.AtomicReference;

public class RaceConditionExample {

    // BROKEN: check-then-act is not atomic
    static class BrokenLazyInit {
        private static Object instance;

        static Object getInstance() {
            if (instance == null) {       // Thread A checks: null
                // Thread B also checks: null
                instance = new Object();  // Both create!
            }
            return instance;
        }
    }

    // FIXED: using AtomicReference with compareAndSet
    static class SafeLazyInit {
        private static final AtomicReference<Object> instance = new AtomicReference<>();

        static Object getInstance() {
            Object current = instance.get();
            if (current == null) {
                Object newInstance = new Object();
                if (instance.compareAndSet(null, newInstance)) {
                    return newInstance; // We won the race
                }
                return instance.get(); // Someone else won
            }
            return current;
        }
    }

    // BROKEN: read-modify-write is not atomic
    static int unsafeCounter = 0;

    // FIXED: use AtomicInteger or synchronized
    static java.util.concurrent.atomic.AtomicInteger safeCounter =
        new java.util.concurrent.atomic.AtomicInteger(0);

    public static void main(String[] args) throws InterruptedException {
        Thread[] threads = new Thread[100];
        for (int i = 0; i < 100; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    unsafeCounter++;           // NOT atomic: read + increment + write
                    safeCounter.incrementAndGet(); // Atomic CAS operation
                }
            });
            threads[i].start();
        }
        for (Thread t : threads) t.join();

        System.out.println("Unsafe counter: " + unsafeCounter + " (expected 100000)");
        System.out.println("Safe counter:   " + safeCounter.get() + " (always 100000)");
    }
}
```

---

### Memory Visibility: Without volatile/synchronized

```java
public class VisibilityProblem {

    // Without volatile, running thread might NEVER see the update
    // JIT can hoist the read of 'running' out of the loop
    private static volatile boolean running = true;

    public static void main(String[] args) throws InterruptedException {
        Thread worker = new Thread(() -> {
            int count = 0;
            while (running) {  // Without volatile, might loop forever
                count++;
            }
            System.out.println("Worker stopped. Count: " + count);
        });

        worker.start();
        Thread.sleep(1000);
        running = false; // Without volatile, worker might never see this
        System.out.println("Main set running = false");
        worker.join(3000);

        if (worker.isAlive()) {
            System.out.println("Worker STILL running — visibility bug!");
            worker.interrupt();
        }
    }
}
```

**Why this happens without `volatile`:**
- Each CPU core has its own cache. Without a memory barrier (volatile/synchronized), changes to shared variables may remain in the writing thread's cache indefinitely.
- The JIT compiler may also optimize the `while(running)` loop into `while(true)` if it determines `running` is never modified within the loop body (from that thread's perspective).
- `volatile` guarantees: writes are immediately flushed to main memory, reads always fetch from main memory.

---

## Quick Reference: When to Use What

| Problem | Best Tool | Why |
|---------|-----------|-----|
| Producer-Consumer | `BlockingQueue` | All synchronization built-in |
| Reader-Writer | `ReentrantReadWriteLock` | Concurrent reads, exclusive writes |
| High-read, low-write | `StampedLock` | Optimistic reads avoid locking |
| Resource pool | `Semaphore` | Limit concurrent access count |
| Wait for N events | `CountDownLatch` | One-shot countdown |
| Phased computation | `CyclicBarrier` | Reusable sync point |
| Dynamic phases | `Phaser` | Register/deregister on the fly |
| Divide and conquer | `ForkJoinPool` | Work-stealing for recursive tasks |
| Simple mutual exclusion | `synchronized` | Low overhead, familiar |
| Need tryLock/timeout | `ReentrantLock` | More control than synchronized |
| Lock-free counter | `AtomicInteger` | CAS-based, no blocking |
| Visibility only | `volatile` | Cheapest memory barrier |
