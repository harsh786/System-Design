import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem35_OptimisticLockingCounter {
    /**
     * Problem: Optimistic Locking Counter
     * Counter using version-based optimistic locking (retry on conflict).
     * Time: O(1) amortized | Space: O(1)
     * Production Analogy: Database optimistic concurrency control (ETag-based updates).
     */
    private volatile long value = 0;
    private volatile long version = 0;

    public synchronized long[] read() { return new long[]{value, version}; }

    public synchronized boolean write(long newValue, long expectedVersion) {
        if (version != expectedVersion) return false;
        value = newValue;
        version++;
        return true;
    }

    public void increment() {
        while (true) {
            long[] state = read();
            if (write(state[0] + 1, state[1])) break;
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem35_OptimisticLockingCounter counter = new Problem35_OptimisticLockingCounter();
        Thread[] ts = new Thread[4];
        for (int i = 0; i < 4; i++) { ts[i] = new Thread(() -> { for (int j = 0; j < 1000; j++) counter.increment(); }); ts[i].start(); }
        for (Thread t : ts) t.join();
        System.out.println("Counter: " + counter.value + " (expected 4000)");
    }
}
