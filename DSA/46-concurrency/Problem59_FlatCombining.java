import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.*;

/**
 * Problem 59: Flat Combining (Batching Concurrent Operations)
 * 
 * REAL-WORLD USAGE:
 * - Redis single-threaded model (one thread executes all ops in batch)
 * - Database group commit (batch fsync for multiple transactions)
 * - Network packet coalescing (Nagle's algorithm concept)
 * - Linux kernel futex (one thread handles multiple waiters)
 * 
 * KEY CONCEPTS:
 * - Instead of each thread fighting for a lock, threads POST their operations
 *   to a publication list, then ONE thread (the combiner) executes all of them
 * - The combiner holds the lock for the duration of the batch
 * - Other threads spin-wait for their operation to be completed
 * - Amortizes lock acquisition cost across many operations
 * 
 * WHY IT'S FAST:
 * 1. Only ONE cache-line transfer for the lock (not N threads bouncing it)
 * 2. Combiner has exclusive cache access to the data structure (no contention)
 * 3. Sequential access patterns are CPU-friendly (prefetcher works well)
 * 4. Reduces context switches (threads spin briefly rather than block)
 * 
 * MEMORY ORDERING:
 * - Publication: thread writes operation, then sets flag (release)
 * - Combiner reads flag (acquire), executes op, writes result, clears flag (release)
 * - Waiting thread reads flag (acquire) to see result
 * 
 * PITFALLS:
 * 1. Unfair: combiner thread does all the work (but throughput is higher)
 * 2. If combiner is slow, all threads are blocked
 * 3. Publication list traversal is O(threads) - limit thread count
 * 4. Thread must clean up its slot when done (to avoid stale entries)
 */
public class Problem59_FlatCombining {

    // ==================== OPERATION RECORD ====================
    static class OperationRecord<R> {
        enum State { EMPTY, PENDING, COMPLETED }
        volatile State state = State.EMPTY;
        volatile int opType; // 0=push, 1=pop, 2=peek
        volatile Object argument;
        volatile R result;
        volatile boolean active = false; // is this slot in use by a thread?
    }

    // ==================== FLAT-COMBINED STACK ====================
    static class FlatCombinedStack<T> {
        private final Deque<T> stack = new ArrayDeque<>(); // Protected data structure
        private final AtomicBoolean globalLock = new AtomicBoolean(false);
        private static final int MAX_THREADS = 64;
        @SuppressWarnings("unchecked")
        private final OperationRecord<T>[] publicationList = new OperationRecord[MAX_THREADS];
        private final AtomicInteger slotCounter = new AtomicInteger(0);
        private final ThreadLocal<Integer> threadSlot = ThreadLocal.withInitial(() -> {
            int slot = slotCounter.getAndIncrement();
            publicationList[slot] = new OperationRecord<>();
            publicationList[slot].active = true;
            return slot;
        });

        private static final int COMBINING_PASSES = 2; // Multiple passes catch late arrivals

        /**
         * Submit an operation and wait for result.
         * If this thread becomes the combiner, it executes everyone's operations.
         */
        @SuppressWarnings("unchecked")
        private T submitOp(int opType, Object argument) {
            int slot = threadSlot.get();
            OperationRecord<T> record = publicationList[slot];

            // Publish operation
            record.argument = argument;
            record.opType = opType;
            record.state = OperationRecord.State.PENDING; // Release

            // Try to become the combiner
            if (globalLock.compareAndSet(false, true)) {
                // WE are the combiner - execute everyone's operations
                combine();
                globalLock.set(false);
            } else {
                // Wait for combiner to handle our operation
                while (record.state == OperationRecord.State.PENDING) {
                    Thread.onSpinWait();
                }
            }

            T result = record.result;
            record.state = OperationRecord.State.EMPTY;
            return result;
        }

        /**
         * Combiner: scan publication list and execute all pending operations.
         * This runs with exclusive access to the data structure.
         */
        @SuppressWarnings("unchecked")
        private void combine() {
            for (int pass = 0; pass < COMBINING_PASSES; pass++) {
                for (int i = 0; i < slotCounter.get(); i++) {
                    OperationRecord<T> record = publicationList[i];
                    if (record != null && record.state == OperationRecord.State.PENDING) {
                        // Execute the operation on the data structure
                        switch (record.opType) {
                            case 0: // push
                                stack.push((T) record.argument);
                                record.result = null;
                                break;
                            case 1: // pop
                                record.result = stack.isEmpty() ? null : stack.pop();
                                break;
                            case 2: // peek
                                record.result = stack.isEmpty() ? null : stack.peek();
                                break;
                        }
                        record.state = OperationRecord.State.COMPLETED; // Release - notify waiter
                    }
                }
            }
        }

        public void push(T item) { submitOp(0, item); }
        public T pop() { return submitOp(1, null); }
        public T peek() { return submitOp(2, null); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Flat Combining Stress Test ===\n");

        FlatCombinedStack<Integer> stack = new FlatCombinedStack<>();
        int numThreads = 8;
        int opsPerThread = 500_000;
        AtomicInteger pushCount = new AtomicInteger(0);
        AtomicInteger popCount = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < opsPerThread; i++) {
                    if (i % 2 == 0) {
                        stack.push(i);
                        pushCount.incrementAndGet();
                    } else {
                        if (stack.pop() != null) {
                            popCount.incrementAndGet();
                        }
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        // Drain
        int remaining = 0;
        while (stack.pop() != null) remaining++;

        System.out.println("Threads: " + numThreads + ", Ops/thread: " + opsPerThread);
        System.out.println("Pushes: " + pushCount.get() + ", Pops: " + popCount.get());
        System.out.println("Remaining: " + remaining);
        System.out.println("Integrity (push == pop + remaining): " + (pushCount.get() == popCount.get() + remaining));
        System.out.println("Total ops: " + (numThreads * opsPerThread));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + ((long)numThreads * opsPerThread * 1_000_000_000L / elapsed) + " ops/sec");
        System.out.println("\nKey insight: One thread does all the work → no cache-line bouncing.");
        System.out.println("Similar to Redis's single-threaded model achieving millions of ops/sec.");
    }
}
