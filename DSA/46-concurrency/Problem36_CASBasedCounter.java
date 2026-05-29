import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem36_CASBasedCounter {
    /**
     * Problem: CAS-based Counter (AtomicInteger)
     * Lock-free counter using Compare-And-Swap.
     * Time: O(1) amortized | Space: O(1)
     * Production Analogy: High-throughput metrics counters in monitoring systems.
     */
    private final AtomicInteger counter = new AtomicInteger(0);

    public void increment() { counter.incrementAndGet(); }
    public void decrement() { counter.decrementAndGet(); }
    public int get() { return counter.get(); }

    // Manual CAS loop demonstration
    public void addWithCAS(int delta) {
        int expected;
        do { expected = counter.get(); } while (!counter.compareAndSet(expected, expected + delta));
    }

    public static void main(String[] args) throws InterruptedException {
        Problem36_CASBasedCounter c = new Problem36_CASBasedCounter();
        Thread[] ts = new Thread[8];
        for (int i = 0; i < 8; i++) { ts[i] = new Thread(() -> { for (int j = 0; j < 1000; j++) c.increment(); }); ts[i].start(); }
        for (Thread t : ts) t.join();
        System.out.println("Counter: " + c.get() + " (expected 8000)");
    }
}
