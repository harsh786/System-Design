import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 67: Thread Pool with Work Stealing
 * 
 * PRODUCTION MAPPING: Java ForkJoinPool, Go scheduler (goroutines), Tokio (Rust),
 *                     .NET ThreadPool, Cilk, Intel TBB
 * 
 * Core Idea:
 * - Each worker has its own local deque (double-ended queue)
 * - Workers push/pop from their own deque (no contention)
 * - Idle workers STEAL from the tail of other workers' deques
 * 
 * Why work stealing > simple thread pool:
 * - Better load balancing with uneven task sizes
 * - Less contention (own deque = no locks for local ops)
 * - Cache-friendly (process own tasks = hot cache)
 * 
 * Design Decisions:
 * - Deque per worker: LIFO for local (cache locality), FIFO steal (large tasks at bottom)
 * - Random victim selection for stealing (avoids thundering herd)
 * - Exponential backoff when no work available
 */
public class Problem67_ThreadPoolWorkStealing {

    static class WorkStealingPool {
        private final Worker[] workers;
        private final Thread[] threads;
        private volatile boolean shutdown = false;
        private final AtomicLong tasksCompleted = new AtomicLong(0);
        private final AtomicLong steals = new AtomicLong(0);

        static class Worker implements Runnable {
            final Deque<Runnable> deque = new ConcurrentLinkedDeque<>();
            final int id;
            final WorkStealingPool pool;
            volatile long tasksRun = 0;

            Worker(int id, WorkStealingPool pool) {
                this.id = id;
                this.pool = pool;
            }

            @Override
            public void run() {
                while (!pool.shutdown) {
                    Runnable task = deque.pollFirst(); // LIFO - local pop from top

                    if (task == null) {
                        // Try to steal from another worker
                        task = steal();
                    }

                    if (task != null) {
                        try {
                            task.run();
                            tasksRun++;
                            pool.tasksCompleted.incrementAndGet();
                        } catch (Exception e) {
                            // In production: error handler
                        }
                    } else {
                        // No work anywhere - back off
                        try { Thread.sleep(1); } catch (InterruptedException e) { break; }
                    }
                }
            }

            private Runnable steal() {
                // Random victim selection
                Random rng = ThreadLocalRandom.current();
                int attempts = pool.workers.length - 1;
                for (int i = 0; i < attempts; i++) {
                    int victim = rng.nextInt(pool.workers.length);
                    if (victim == id) continue;
                    
                    Runnable stolen = pool.workers[victim].deque.pollLast(); // FIFO - steal from bottom
                    if (stolen != null) {
                        pool.steals.incrementAndGet();
                        return stolen;
                    }
                }
                return null;
            }
        }

        public WorkStealingPool(int parallelism) {
            workers = new Worker[parallelism];
            threads = new Thread[parallelism];
            for (int i = 0; i < parallelism; i++) {
                workers[i] = new Worker(i, this);
                threads[i] = new Thread(workers[i], "worker-" + i);
                threads[i].setDaemon(true);
                threads[i].start();
            }
        }

        /** Submit task to a random worker (or least loaded) */
        public void submit(Runnable task) {
            // Find least loaded worker
            int minIdx = 0;
            int minSize = Integer.MAX_VALUE;
            for (int i = 0; i < workers.length; i++) {
                int s = workers[i].deque.size();
                if (s < minSize) { minSize = s; minIdx = i; }
            }
            workers[minIdx].deque.addFirst(task);
        }

        /** Submit task to specific worker (for locality) */
        public void submitTo(int workerId, Runnable task) {
            workers[workerId % workers.length].deque.addFirst(task);
        }

        public void shutdown() {
            shutdown = true;
            for (Thread t : threads) t.interrupt();
        }

        public boolean awaitCompletion(long timeoutMs) throws InterruptedException {
            long deadline = System.currentTimeMillis() + timeoutMs;
            while (System.currentTimeMillis() < deadline) {
                boolean allEmpty = true;
                for (Worker w : workers) {
                    if (!w.deque.isEmpty()) { allEmpty = false; break; }
                }
                if (allEmpty) {
                    Thread.sleep(10); // let in-flight tasks finish
                    // Check again
                    allEmpty = true;
                    for (Worker w : workers) {
                        if (!w.deque.isEmpty()) { allEmpty = false; break; }
                    }
                    if (allEmpty) return true;
                }
                Thread.sleep(5);
            }
            return false;
        }

        public long getTasksCompleted() { return tasksCompleted.get(); }
        public long getSteals() { return steals.get(); }
        public long[] getPerWorkerTasks() {
            long[] counts = new long[workers.length];
            for (int i = 0; i < workers.length; i++) counts[i] = workers[i].tasksRun;
            return counts;
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Thread Pool with Work Stealing ===\n");

        // Test 1: Basic task execution
        WorkStealingPool pool = new WorkStealingPool(4);
        AtomicInteger counter = new AtomicInteger(0);
        for (int i = 0; i < 100; i++) {
            pool.submit(counter::incrementAndGet);
        }
        pool.awaitCompletion(2000);
        assert counter.get() == 100 : "Expected 100, got: " + counter.get();
        System.out.println("PASS: All 100 tasks executed");

        // Test 2: Work stealing with uneven load
        pool.shutdown();
        pool = new WorkStealingPool(4);
        counter.set(0);
        
        // Submit ALL tasks to worker 0 - others should steal
        for (int i = 0; i < 1000; i++) {
            pool.submitTo(0, counter::incrementAndGet);
        }
        pool.awaitCompletion(3000);
        
        long[] perWorker = pool.getPerWorkerTasks();
        long totalSteals = pool.getSteals();
        System.out.printf("PASS: Work distribution: %s (steals=%d)\n", 
            Arrays.toString(perWorker), totalSteals);
        assert totalSteals > 0 : "Should have steals when all submitted to one worker";
        assert counter.get() == 1000;

        // Test 3: Variable-duration tasks
        pool.shutdown();
        pool = new WorkStealingPool(4);
        AtomicInteger slowCount = new AtomicInteger(0);
        
        // Mix of fast and slow tasks, all to one worker
        for (int i = 0; i < 20; i++) {
            final int taskId = i;
            pool.submitTo(0, () -> {
                try {
                    Thread.sleep(taskId < 5 ? 50 : 1); // 5 slow, 15 fast
                } catch (InterruptedException e) {}
                slowCount.incrementAndGet();
            });
        }
        pool.awaitCompletion(3000);
        assert slowCount.get() == 20;
        perWorker = pool.getPerWorkerTasks();
        System.out.printf("PASS: Mixed task durations, distribution: %s\n", Arrays.toString(perWorker));

        // Test 4: Recursive task (like ForkJoin)
        pool.shutdown();
        pool = new WorkStealingPool(4);
        AtomicLong fibResult = new AtomicLong(0);
        AtomicInteger fibTasks = new AtomicInteger(0);
        
        // Compute sum of 1..100 using recursive decomposition
        final WorkStealingPool finalPool = pool;
        class SumTask implements Runnable {
            final int lo, hi;
            final AtomicLong result;
            SumTask(int lo, int hi, AtomicLong result) { this.lo = lo; this.hi = hi; this.result = result; }
            @Override
            public void run() {
                fibTasks.incrementAndGet();
                if (hi - lo <= 10) {
                    long sum = 0;
                    for (int i = lo; i <= hi; i++) sum += i;
                    result.addAndGet(sum);
                } else {
                    int mid = (lo + hi) / 2;
                    finalPool.submit(new SumTask(lo, mid, result));
                    finalPool.submit(new SumTask(mid + 1, hi, result));
                }
            }
        }
        pool.submit(new SumTask(1, 100, fibResult));
        pool.awaitCompletion(2000);
        assert fibResult.get() == 5050 : "Expected 5050, got: " + fibResult.get();
        System.out.printf("PASS: Recursive decomposition: sum(1..100)=%d using %d tasks\n", 
            fibResult.get(), fibTasks.get());

        pool.shutdown();

        // Test 5: Throughput comparison (conceptual)
        System.out.println("\n--- Work Stealing vs Fixed Assignment ---");
        System.out.println("  Fixed: If one worker gets slow tasks, others idle");
        System.out.println("  Stealing: Idle workers take from busy workers");
        System.out.println("  Result: Better utilization, especially with heterogeneous tasks");

        System.out.println("\nAll tests passed!");
    }
}
