import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 49: Design Thread-Safe Counter
 * 
 * API Contract:
 * - increment(): Atomically increment
 * - decrement(): Atomically decrement
 * - get(): Return current value
 * - incrementBy(n): Add n atomically
 * 
 * Multiple implementations shown: synchronized, AtomicInteger, LongAdder
 * Complexity: O(1) for all operations
 * 
 * Production Analogy: Prometheus counters, metrics collection,
 * connection pool size tracking, request counting for rate limiting
 */
public class Problem49_DesignThreadSafeCounter {

    // Implementation 1: Using AtomicInteger (CAS-based, lock-free)
    static class AtomicCounter {
        private AtomicInteger count = new AtomicInteger(0);

        public void increment() { count.incrementAndGet(); }
        public void decrement() { count.decrementAndGet(); }
        public int get() { return count.get(); }
        public void incrementBy(int n) { count.addAndGet(n); }
    }

    // Implementation 2: Using synchronized (for comparison)
    static class SyncCounter {
        private int count = 0;

        public synchronized void increment() { count++; }
        public synchronized void decrement() { count--; }
        public synchronized int get() { return count; }
        public synchronized void incrementBy(int n) { count += n; }
    }

    // Implementation 3: LongAdder for high-contention scenarios
    // (striped cells reduce contention vs single AtomicLong)
    static class StripedCounter {
        private LongAdder adder = new LongAdder();

        public void increment() { adder.increment(); }
        public void decrement() { adder.decrement(); }
        public long get() { return adder.sum(); }
        public void incrementBy(long n) { adder.add(n); }
    }

    public static void main(String[] args) throws Exception {
        // Single-threaded correctness
        AtomicCounter ac = new AtomicCounter();
        ac.increment(); ac.increment(); ac.decrement();
        assert ac.get() == 1;
        ac.incrementBy(9);
        assert ac.get() == 10;

        // Multi-threaded correctness test
        AtomicCounter counter = new AtomicCounter();
        int numThreads = 10;
        int perThread = 1000;
        ExecutorService exec = Executors.newFixedThreadPool(numThreads);
        CountDownLatch latch = new CountDownLatch(numThreads);

        for (int i = 0; i < numThreads; i++) {
            exec.submit(() -> {
                for (int j = 0; j < perThread; j++) counter.increment();
                latch.countDown();
            });
        }
        latch.await();
        exec.shutdown();
        assert counter.get() == numThreads * perThread;

        // LongAdder test
        StripedCounter sc = new StripedCounter();
        sc.increment(); sc.increment(); sc.decrement();
        assert sc.get() == 1;

        System.out.println("All tests passed!");
    }
}
