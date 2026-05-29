import java.util.concurrent.atomic.*;
import java.util.concurrent.*;

/**
 * Problem 58: Work Stealing Deque (Chase-Lev Algorithm)
 * 
 * REAL-WORLD USAGE:
 * - Java ForkJoinPool (the backbone of parallel streams, CompletableFuture)
 * - Go runtime scheduler (goroutine scheduling)
 * - Cilk (MIT's parallel programming framework)
 * - Tokio (Rust async runtime) work-stealing scheduler
 * - Intel TBB (Threading Building Blocks)
 * 
 * KEY CONCEPTS:
 * - Each worker thread has its own deque (double-ended queue)
 * - Owner pushes/pops from the BOTTOM (LIFO - cache-friendly)
 * - Thieves steal from the TOP (FIFO - steal oldest/largest work)
 * - Only one owner, but multiple thieves → asymmetric synchronization
 * 
 * WHY LIFO FOR OWNER, FIFO FOR THIEF?
 * - Owner's recent work is hot in cache (temporal locality)
 * - Oldest work tends to be largest (not yet subdivided) → thief gets more work
 * 
 * MEMORY ORDERING:
 * - bottom is only written by owner → relaxed store okay
 * - top is contended (thieves CAS it) → needs CAS with sequential consistency
 * - Array accesses need at least release/acquire between push and steal
 * - The critical ordering: bottom write in push must be visible before top read in pop
 * 
 * PITFALLS:
 * 1. Resizing the circular buffer requires careful epoch-based reclamation
 * 2. Pop and steal can conflict on the LAST element → CAS arbitrates
 * 3. ABA on top counter → use long counter (practically no wraparound)
 * 4. Memory fences between bottom update and array write are critical
 */
public class Problem58_WorkStealingDeque {

    // ==================== CHASE-LEV WORK-STEALING DEQUE ====================
    static class WorkStealingDeque<T> {
        private static final int INITIAL_CAPACITY = 1024;
        private volatile AtomicReferenceArray<T> array;
        private final AtomicLong top = new AtomicLong(0);    // Thieves steal from here
        private volatile long bottom = 0;                     // Owner pushes/pops here
        private volatile int capacity = INITIAL_CAPACITY;

        @SuppressWarnings("unchecked")
        WorkStealingDeque() {
            array = new AtomicReferenceArray<>(INITIAL_CAPACITY);
        }

        /**
         * PUSH: Only called by owner thread.
         * Adds to the bottom of the deque.
         */
        public void push(T item) {
            long b = bottom;
            long t = top.get();
            int size = (int)(b - t);

            if (size >= capacity - 1) {
                resize(); // Grow the array
            }

            array.set((int)(b % capacity), item);
            // StoreStore barrier: ensure item is written before bottom is updated
            // (volatile write to bottom provides this in Java)
            bottom = b + 1;
        }

        /**
         * POP: Only called by owner thread.
         * Removes from the bottom (LIFO). May conflict with steal on last element.
         */
        public T pop() {
            long b = bottom - 1;
            bottom = b; // Announce intention to pop (StoreLoad barrier needed)

            long t = top.get();
            int size = (int)(b - t);

            if (size < 0) {
                // Deque was already empty
                bottom = t;
                return null;
            }

            T item = array.get((int)(b % capacity));

            if (size > 0) {
                // More than one item - no conflict possible
                return item;
            }

            // Exactly one item left - may conflict with a thief
            // CAS to arbitrate: whoever wins gets the item
            if (!top.compareAndSet(t, t + 1)) {
                // Thief won - item is gone
                item = null;
            }
            bottom = t + 1;
            return item;
        }

        /**
         * STEAL: Called by other threads (thieves).
         * Removes from the top (FIFO). Lock-free via CAS.
         */
        public T steal() {
            long t = top.get();
            // LoadLoad barrier (volatile read of bottom)
            long b = bottom;

            int size = (int)(b - t);
            if (size <= 0) {
                return null; // Empty
            }

            T item = array.get((int)(t % capacity));

            // CAS to claim this slot
            if (!top.compareAndSet(t, t + 1)) {
                // Another thief (or owner's pop) beat us
                return null;
            }
            return item;
        }

        public int size() {
            return Math.max(0, (int)(bottom - top.get()));
        }

        private void resize() {
            int newCapacity = capacity * 2;
            AtomicReferenceArray<T> newArray = new AtomicReferenceArray<>(newCapacity);
            long t = top.get();
            long b = bottom;
            for (long i = t; i < b; i++) {
                newArray.set((int)(i % newCapacity), array.get((int)(i % capacity)));
            }
            array = newArray;
            capacity = newCapacity;
        }
    }

    // ==================== WORK STEALING SCHEDULER ====================
    static class WorkStealingScheduler {
        private final WorkStealingDeque<Runnable>[] deques;
        private final Thread[] workers;
        private volatile boolean shutdown = false;
        private final AtomicLong tasksCompleted = new AtomicLong(0);
        private final AtomicLong steals = new AtomicLong(0);

        @SuppressWarnings("unchecked")
        WorkStealingScheduler(int numWorkers) {
            deques = new WorkStealingDeque[numWorkers];
            workers = new Thread[numWorkers];
            for (int i = 0; i < numWorkers; i++) {
                deques[i] = new WorkStealingDeque<>();
            }
            for (int i = 0; i < numWorkers; i++) {
                final int workerId = i;
                workers[i] = new Thread(() -> workerLoop(workerId), "Worker-" + i);
                workers[i].setDaemon(true);
                workers[i].start();
            }
        }

        private void workerLoop(int id) {
            while (!shutdown) {
                // Try own deque first (LIFO - cache friendly)
                Runnable task = deques[id].pop();
                if (task != null) {
                    task.run();
                    tasksCompleted.incrementAndGet();
                    continue;
                }
                // Own deque empty - try stealing from others (FIFO - get big chunks)
                boolean stolen = false;
                for (int i = 0; i < deques.length; i++) {
                    if (i == id) continue;
                    task = deques[i].steal();
                    if (task != null) {
                        task.run();
                        tasksCompleted.incrementAndGet();
                        steals.incrementAndGet();
                        stolen = true;
                        break;
                    }
                }
                if (!stolen) {
                    Thread.onSpinWait();
                }
            }
        }

        public void submit(int workerId, Runnable task) {
            deques[workerId % deques.length].push(task);
        }

        public void shutdown() throws InterruptedException {
            shutdown = true;
            for (Thread w : workers) w.join(1000);
        }

        public long getTasksCompleted() { return tasksCompleted.get(); }
        public long getSteals() { return steals.get(); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Work Stealing Deque (Chase-Lev) ===\n");

        // Test 1: Basic correctness
        System.out.println("--- Basic Deque Test ---");
        WorkStealingDeque<Integer> deque = new WorkStealingDeque<>();
        for (int i = 0; i < 100; i++) deque.push(i);
        System.out.println("Size after 100 pushes: " + deque.size());
        int popped = 0;
        while (deque.pop() != null) popped++;
        System.out.println("Popped: " + popped);

        // Test 2: Concurrent owner + thieves
        System.out.println("\n--- Concurrent Owner + Thieves ---");
        WorkStealingDeque<Integer> sharedDeque = new WorkStealingDeque<>();
        int numItems = 1_000_000;
        AtomicInteger totalRetrieved = new AtomicInteger(0);
        CountDownLatch done = new CountDownLatch(5); // 1 owner + 4 thieves

        // Owner pushes and pops
        new Thread(() -> {
            for (int i = 0; i < numItems; i++) {
                sharedDeque.push(i);
                if (i % 3 == 0) { // Pop every 3rd push
                    if (sharedDeque.pop() != null) totalRetrieved.incrementAndGet();
                }
            }
            done.countDown();
        }).start();

        // Thieves
        for (int t = 0; t < 4; t++) {
            new Thread(() -> {
                while (done.getCount() > 1 || sharedDeque.size() > 0) {
                    Integer item = sharedDeque.steal();
                    if (item != null) totalRetrieved.incrementAndGet();
                    else Thread.onSpinWait();
                }
                done.countDown();
            }).start();
        }

        done.await();
        // Drain remaining
        while (sharedDeque.pop() != null) totalRetrieved.incrementAndGet();
        System.out.println("Total items produced: " + numItems);
        System.out.println("Total items retrieved: " + totalRetrieved.get());

        // Test 3: Work stealing scheduler
        System.out.println("\n--- Work Stealing Scheduler ---");
        int numWorkers = 4;
        WorkStealingScheduler scheduler = new WorkStealingScheduler(numWorkers);
        int totalTasks = 500_000;
        AtomicLong computeSum = new AtomicLong(0);
        CountDownLatch allDone = new CountDownLatch(totalTasks);

        long start = System.nanoTime();
        // Submit all tasks to worker 0 (highly imbalanced)
        for (int i = 0; i < totalTasks; i++) {
            final int val = i;
            scheduler.submit(0, () -> {
                computeSum.addAndGet(val);
                allDone.countDown();
            });
        }

        allDone.await();
        long elapsed = System.nanoTime() - start;
        scheduler.shutdown();

        System.out.println("Tasks: " + totalTasks + " (all submitted to worker 0)");
        System.out.println("Workers: " + numWorkers);
        System.out.println("Tasks completed: " + scheduler.getTasksCompleted());
        System.out.println("Work steals: " + scheduler.getSteals());
        System.out.println("Expected sum: " + ((long)totalTasks * (totalTasks-1) / 2));
        System.out.println("Actual sum: " + computeSum.get());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("\nKey insight: ForkJoinPool uses this exact pattern.");
        System.out.println("Load balancing happens automatically via stealing.");
    }
}
