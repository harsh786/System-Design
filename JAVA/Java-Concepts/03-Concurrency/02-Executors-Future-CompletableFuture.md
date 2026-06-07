# Executors, Future, CompletableFuture & Concurrency Utilities

## 1. Executor Framework

### 1.1 Executor Interfaces Hierarchy

```java
/*
┌─────────────┐
│  Executor   │  - Single method: execute(Runnable)
└──────┬──────┘
       │ extends
┌──────▼──────────────┐
│  ExecutorService    │  - submit(), shutdown(), invokeAll(), invokeAny()
└──────┬──────────────┘
       │ extends
┌──────▼──────────────────────┐
│  ScheduledExecutorService   │  - schedule(), scheduleAtFixedRate()
└─────────────────────────────┘
*/

import java.util.concurrent.*;
import java.util.*;

public class ExecutorInterfacesDemo {
    
    public static void main(String[] args) throws Exception {
        
        // ==================== Executor (simplest) ====================
        Executor executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> System.out.println("Simple execution"));
        
        // ==================== ExecutorService ====================
        ExecutorService service = Executors.newFixedThreadPool(4);
        
        // submit with Runnable
        Future<?> future1 = service.submit(() -> System.out.println("Runnable task"));
        
        // submit with Callable (returns result)
        Future<String> future2 = service.submit(() -> {
            Thread.sleep(1000);
            return "Result from callable";
        });
        
        System.out.println(future2.get()); // Blocks until result is ready
        
        // invokeAll - submit all, wait for all to complete
        List<Callable<Integer>> tasks = List.of(
            () -> { Thread.sleep(1000); return 1; },
            () -> { Thread.sleep(2000); return 2; },
            () -> { Thread.sleep(500);  return 3; }
        );
        
        List<Future<Integer>> results = service.invokeAll(tasks); // Blocks until ALL done
        for (Future<Integer> f : results) {
            System.out.println("Result: " + f.get());
        }
        // Output: 1, 2, 3 (order preserved, not completion order)
        
        // invokeAny - returns first successfully completed result
        Integer fastest = service.invokeAny(tasks); // Returns 3 (500ms is fastest)
        System.out.println("Fastest: " + fastest);
        
        // Shutdown
        service.shutdown();           // No new tasks, finish existing
        service.awaitTermination(5, TimeUnit.SECONDS); // Wait for completion
        // service.shutdownNow();     // Interrupt all running tasks, return unstarted
        
        // ==================== ScheduledExecutorService ====================
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
        
        // Run once after delay
        scheduler.schedule(() -> System.out.println("Delayed task"), 
                          2, TimeUnit.SECONDS);
        
        // Run repeatedly at fixed rate (every 1 second)
        ScheduledFuture<?> periodic = scheduler.scheduleAtFixedRate(
            () -> System.out.println("Periodic: " + System.currentTimeMillis()),
            0,    // initial delay
            1,    // period
            TimeUnit.SECONDS
        );
        
        // Run repeatedly with fixed delay between end of one and start of next
        scheduler.scheduleWithFixedDelay(
            () -> {
                System.out.println("Fixed delay task");
                try { Thread.sleep(500); } catch (InterruptedException e) {}
            },
            0,    // initial delay
            1,    // delay after previous task completes
            TimeUnit.SECONDS
        );
        
        Thread.sleep(5000);
        periodic.cancel(false); // Stop periodic task
        scheduler.shutdown();
    }
}
```

### 1.2 ThreadPoolExecutor Internals

```java
import java.util.concurrent.*;

public class ThreadPoolExecutorDemo {
    
    /*
    ThreadPoolExecutor(
        int corePoolSize,      - Threads always kept alive (even idle)
        int maximumPoolSize,   - Maximum threads allowed
        long keepAliveTime,    - Idle time before non-core threads die
        TimeUnit unit,         - Time unit for keepAliveTime
        BlockingQueue<Runnable> workQueue,  - Queue for pending tasks
        ThreadFactory threadFactory,        - Creates new threads
        RejectedExecutionHandler handler   - When queue is full & max threads reached
    )
    
    EXECUTION FLOW:
    1. Task submitted
    2. If threads < corePoolSize → create new thread
    3. If threads >= corePoolSize → add to queue
    4. If queue is full AND threads < maxPoolSize → create new thread
    5. If queue is full AND threads >= maxPoolSize → reject task
    */
    
    public static void main(String[] args) throws InterruptedException {
        
        // Custom ThreadPoolExecutor
        ThreadPoolExecutor executor = new ThreadPoolExecutor(
            2,                              // corePoolSize
            4,                              // maximumPoolSize
            60L, TimeUnit.SECONDS,          // keepAliveTime for non-core threads
            new ArrayBlockingQueue<>(2),    // workQueue (bounded, capacity 2)
            new CustomThreadFactory(),      // threadFactory
            new ThreadPoolExecutor.CallerRunsPolicy() // rejectionHandler
        );
        
        // Optional: allow core threads to timeout too
        executor.allowCoreThreadTimeOut(true);
        
        // Submit 8 tasks to see the behavior
        for (int i = 1; i <= 8; i++) {
            final int taskId = i;
            try {
                executor.execute(() -> {
                    System.out.println("Task " + taskId + " running on " 
                                     + Thread.currentThread().getName());
                    try { Thread.sleep(2000); } catch (InterruptedException e) {}
                });
                System.out.println("Submitted task " + taskId 
                    + " | Pool size: " + executor.getPoolSize()
                    + " | Queue size: " + executor.getQueue().size()
                    + " | Active: " + executor.getActiveCount());
            } catch (RejectedExecutionException e) {
                System.out.println("Task " + taskId + " REJECTED");
            }
        }
        
        /*
        Task 1: corePoolSize < 2, create thread → pool=1
        Task 2: corePoolSize < 2, create thread → pool=2
        Task 3: queue not full, enqueue → queue=1
        Task 4: queue not full, enqueue → queue=2
        Task 5: queue full, pool < max(4), create thread → pool=3
        Task 6: queue full, pool < max(4), create thread → pool=4
        Task 7: queue full, pool = max → REJECT (CallerRunsPolicy runs in main thread)
        Task 8: queue full, pool = max → REJECT
        */
        
        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);
    }
    
    // Custom thread factory
    static class CustomThreadFactory implements ThreadFactory {
        private int count = 0;
        
        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, "MyPool-Thread-" + (++count));
            t.setDaemon(false);
            t.setPriority(Thread.NORM_PRIORITY);
            return t;
        }
    }
}

// ==================== Rejection Policies ====================
/*
┌────────────────────────┬──────────────────────────────────────────────────┐
│ Policy                 │ Behavior                                         │
├────────────────────────┼──────────────────────────────────────────────────┤
│ AbortPolicy (default)  │ Throws RejectedExecutionException                │
│ CallerRunsPolicy       │ Runs task in the calling thread (back-pressure)  │
│ DiscardPolicy          │ Silently drops the task                          │
│ DiscardOldestPolicy    │ Drops oldest task in queue, retries submit       │
│ Custom                 │ Implement RejectedExecutionHandler               │
└────────────────────────┴──────────────────────────────────────────────────┘
*/

class CustomRejectionHandler implements RejectedExecutionHandler {
    @Override
    public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
        System.err.println("Task rejected! Queue size: " + executor.getQueue().size());
        // Could: log, persist to database, put in overflow queue, etc.
    }
}
```

### 1.3 Executors Factory Methods

```java
import java.util.concurrent.*;

public class ExecutorFactoryDemo {
    
    public static void main(String[] args) {
        
        // ==================== newFixedThreadPool ====================
        // Fixed number of threads, unbounded queue (LinkedBlockingQueue)
        // Use for: known number of concurrent tasks
        // Danger: unbounded queue can cause OOM if tasks pile up
        ExecutorService fixed = Executors.newFixedThreadPool(4);
        // Equivalent to: new ThreadPoolExecutor(4, 4, 0L, SECONDS, new LinkedBlockingQueue<>())
        
        // ==================== newCachedThreadPool ====================
        // 0 core threads, Integer.MAX_VALUE max threads, 60s keepalive
        // Use for: many short-lived tasks
        // Danger: can create unlimited threads under load → OOM
        ExecutorService cached = Executors.newCachedThreadPool();
        // Equivalent to: new ThreadPoolExecutor(0, MAX_VALUE, 60L, SECONDS, new SynchronousQueue<>())
        
        // ==================== newSingleThreadExecutor ====================
        // Exactly 1 thread, tasks execute sequentially
        // Use for: sequential task execution, event loop
        // Guarantees task ordering (FIFO)
        ExecutorService single = Executors.newSingleThreadExecutor();
        
        // ==================== newScheduledThreadPool ====================
        // For delayed/periodic tasks
        ScheduledExecutorService scheduled = Executors.newScheduledThreadPool(2);
        
        // ==================== newWorkStealingPool (Java 8) ====================
        // Uses ForkJoinPool, parallelism = available processors
        // Work-stealing: idle threads steal tasks from busy threads' queues
        ExecutorService workStealing = Executors.newWorkStealingPool();
        // Or with explicit parallelism: Executors.newWorkStealingPool(8)
        
        // Cleanup
        fixed.shutdown();
        cached.shutdown();
        single.shutdown();
        scheduled.shutdown();
        workStealing.shutdown();
    }
}
```

### 1.4 ThreadPoolExecutor Lifecycle States

```java
/*
┌────────────────────────────────────────────────────────────────────────────┐
│                  THREAD POOL LIFECYCLE (ctl field)                           │
│                                                                             │
│  State bits stored in top 3 bits of AtomicInteger 'ctl':                   │
│  ctl = (runState << 29) | workerCount                                       │
│                                                                             │
│  ┌─────────┐  shutdown()  ┌──────────┐  queue empty  ┌─────────┐          │
│  │ RUNNING │────────────→│ SHUTDOWN │──────────────→│ TIDYING │          │
│  │  (-1)   │             │   (0)    │   & workers=0 │   (2)   │          │
│  └────┬────┘             └──────────┘               └────┬────┘          │
│       │                                                   │               │
│       │ shutdownNow()     ┌──────────┐                   │               │
│       └──────────────────→│   STOP   │───────────────────┤ workers=0     │
│                           │   (1)    │                   │               │
│                           └──────────┘                   ▼               │
│                                                   ┌────────────┐         │
│                                                   │ TERMINATED │         │
│                                                   │    (3)     │         │
│                                                   └────────────┘         │
│                                                                             │
│  RUNNING:    Accept new tasks, process queued tasks                         │
│  SHUTDOWN:   Don't accept new tasks, but process queued tasks              │
│  STOP:       Don't accept new, don't process queued, interrupt running     │
│  TIDYING:    All tasks terminated, workerCount = 0, about to call          │
│              terminated() hook                                              │
│  TERMINATED: terminated() hook has completed                               │
└────────────────────────────────────────────────────────────────────────────┘
*/

import java.util.concurrent.*;

public class ThreadPoolLifecycleDemo {
    public static void main(String[] args) throws InterruptedException {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
            2, 4, 60, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(10)
        );

        // Pool is RUNNING
        pool.execute(() -> {
            try { Thread.sleep(5000); } catch (InterruptedException e) {}
        });

        // Transition to SHUTDOWN: finish existing, reject new
        pool.shutdown();
        // pool.execute(someTask); // → RejectedExecutionException!

        // Check state
        System.out.println("isShutdown: " + pool.isShutdown());       // true
        System.out.println("isTerminated: " + pool.isTerminated());   // false (tasks still running)

        // Wait for TERMINATED state
        boolean done = pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("isTerminated: " + pool.isTerminated());   // true

        // Alternative: shutdownNow() → STOP state
        // List<Runnable> pending = pool.shutdownNow(); // returns unstarted tasks
    }
}
```

### 1.5 Work Queue Types — Which to Choose

```java
/*
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORK QUEUE COMPARISON                                 │
├───────────────────────┬─────────────────────────────────────────────────────┤
│ Queue                 │ Behavior & Use Case                                  │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ LinkedBlockingQueue   │ Unbounded (or bounded with capacity)                 │
│ (unbounded)           │ Used by: newFixedThreadPool, newSingleThreadExecutor │
│                       │ DANGER: if tasks arrive faster than processing →     │
│                       │ queue grows forever → OOM                            │
│                       │ Use when: task rate is controlled, back-pressure     │
│                       │ exists elsewhere                                      │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ ArrayBlockingQueue    │ Bounded (fixed capacity, must specify)               │
│                       │ Fair or non-fair ordering                             │
│                       │ Use when: you want bounded memory + reject overflow  │
│                       │ Good default for custom ThreadPoolExecutor            │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ SynchronousQueue      │ Zero capacity! (hand-off from producer to consumer)  │
│                       │ Put blocks until a thread takes it (no buffering)    │
│                       │ Used by: newCachedThreadPool                          │
│                       │ Forces thread creation (up to max) for every task    │
│                       │ Use when: you want immediate execution or rejection  │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ PriorityBlockingQueue │ Unbounded, ordered by priority (Comparable/Comparator)│
│                       │ Use when: tasks have different priorities             │
│                       │ Caution: low-priority tasks may starve               │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ DelayQueue            │ Unbounded, element available only after delay expires │
│                       │ Used internally by: ScheduledThreadPoolExecutor       │
│                       │ Use when: scheduled/delayed task execution            │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ LinkedTransferQueue   │ Unbounded, combines SynchronousQueue + LinkedQueue   │
│                       │ transfer() = hand-off if consumer waiting,           │
│                       │ otherwise enqueue                                     │
│                       │ Use when: you want adaptive behavior                  │
└───────────────────────┴─────────────────────────────────────────────────────┘
*/

import java.util.concurrent.*;

public class WorkQueueDemo {
    public static void main(String[] args) {

        // 1. Bounded queue with rejection → safe, predictable memory
        ThreadPoolExecutor bounded = new ThreadPoolExecutor(
            4, 8, 60, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(100),          // max 100 pending tasks
            new ThreadPoolExecutor.CallerRunsPolicy() // back-pressure
        );

        // 2. SynchronousQueue → immediate execution or new thread
        ThreadPoolExecutor immediate = new ThreadPoolExecutor(
            0, Integer.MAX_VALUE, 60, TimeUnit.SECONDS,
            new SynchronousQueue<>()  // no buffering
        );
        // Same as Executors.newCachedThreadPool()

        // 3. Priority queue → high-priority tasks first
        ThreadPoolExecutor priority = new ThreadPoolExecutor(
            2, 2, 0, TimeUnit.SECONDS,
            new PriorityBlockingQueue<>(100) // tasks must be Comparable
        );

        bounded.shutdown();
        immediate.shutdown();
        priority.shutdown();
    }
}
```

### 1.6 Hook Methods (beforeExecute, afterExecute, terminated)

```java
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Extend ThreadPoolExecutor to add monitoring, logging, timing, and error handling.
 * These hooks are called on the WORKER thread, not the submitting thread.
 */
public class InstrumentedThreadPool extends ThreadPoolExecutor {

    // Track execution time per task
    private final ThreadLocal<Long> startTime = new ThreadLocal<>();
    private final AtomicLong totalTime = new AtomicLong(0);
    private final AtomicLong taskCount = new AtomicLong(0);

    public InstrumentedThreadPool(int coreSize, int maxSize, int queueCapacity) {
        super(coreSize, maxSize, 60, TimeUnit.SECONDS,
              new ArrayBlockingQueue<>(queueCapacity),
              new CallerRunsPolicy());
    }

    /**
     * Called BEFORE each task executes on the worker thread.
     * @param t the thread that will run the task
     * @param r the task that will be executed
     */
    @Override
    protected void beforeExecute(Thread t, Runnable r) {
        super.beforeExecute(t, r);
        startTime.set(System.nanoTime());
        System.out.printf("[BEFORE] Task starting on thread %s | Queue size: %d%n",
            t.getName(), getQueue().size());
    }

    /**
     * Called AFTER each task completes (even if exception thrown).
     * @param r the task that was executed
     * @param t the exception (null if completed normally)
     */
    @Override
    protected void afterExecute(Runnable r, Throwable t) {
        try {
            long elapsed = System.nanoTime() - startTime.get();
            totalTime.addAndGet(elapsed);
            taskCount.incrementAndGet();

            if (t != null) {
                System.err.printf("[ERROR] Task failed: %s%n", t.getMessage());
            } else if (r instanceof Future<?>) {
                try {
                    ((Future<?>) r).get(); // extract exception from Future
                } catch (ExecutionException e) {
                    System.err.printf("[ERROR] Task threw: %s%n", e.getCause().getMessage());
                } catch (Exception e) {
                    // CancellationException, InterruptedException
                }
            }

            System.out.printf("[AFTER] Task completed in %.2f ms%n", elapsed / 1_000_000.0);
        } finally {
            super.afterExecute(r, t);
            startTime.remove(); // prevent ThreadLocal leak
        }
    }

    /**
     * Called when the executor has terminated (all tasks done, pool shut down).
     * Useful for final reporting, resource cleanup.
     */
    @Override
    protected void terminated() {
        try {
            long count = taskCount.get();
            double avgMs = count > 0 ? (totalTime.get() / count) / 1_000_000.0 : 0;
            System.out.printf("[TERMINATED] Pool shutdown. Tasks executed: %d, Avg time: %.2f ms%n",
                count, avgMs);
        } finally {
            super.terminated();
        }
    }

    // Convenience: get average task time
    public double getAverageTaskTimeMs() {
        long count = taskCount.get();
        return count > 0 ? (totalTime.get() / count) / 1_000_000.0 : 0;
    }

    // Demo
    public static void main(String[] args) throws InterruptedException {
        InstrumentedThreadPool pool = new InstrumentedThreadPool(2, 4, 10);

        for (int i = 0; i < 5; i++) {
            final int taskId = i;
            pool.submit(() -> {
                System.out.println("Executing task " + taskId);
                try { Thread.sleep(100); } catch (InterruptedException e) {}
                if (taskId == 3) throw new RuntimeException("Task 3 failed!");
            });
        }

        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
    }
}
```

### 1.7 Thread Pool Monitoring

```java
import java.util.concurrent.*;

public class ThreadPoolMonitoring {
    public static void main(String[] args) throws InterruptedException {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
            4, 8, 60, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(50)
        );

        // Submit some tasks
        for (int i = 0; i < 20; i++) {
            pool.execute(() -> {
                try { Thread.sleep(1000); } catch (InterruptedException e) {}
            });
        }

        // Monitor pool state
        System.out.println("=== Thread Pool Metrics ===");
        System.out.println("Pool Size (current threads):    " + pool.getPoolSize());
        System.out.println("Core Pool Size:                 " + pool.getCorePoolSize());
        System.out.println("Maximum Pool Size:              " + pool.getMaximumPoolSize());
        System.out.println("Active Threads (running tasks): " + pool.getActiveCount());
        System.out.println("Queue Size (waiting tasks):     " + pool.getQueue().size());
        System.out.println("Completed Tasks:                " + pool.getCompletedTaskCount());
        System.out.println("Total Tasks (submitted):        " + pool.getTaskCount());
        System.out.println("Largest Pool Size (ever):       " + pool.getLargestPoolSize());
        System.out.println("Is Shutdown:                    " + pool.isShutdown());
        System.out.println("Is Terminating:                 " + pool.isTerminating());
        System.out.println("Is Terminated:                  " + pool.isTerminated());

        /*
        Use these metrics to:
        - Alert if queue size > threshold (back-pressure building up)
        - Alert if active threads = max threads (saturated)
        - Track completed vs submitted (is pool keeping up?)
        - Report to Prometheus/Grafana for dashboards
        */

        pool.shutdown();
        pool.awaitTermination(30, TimeUnit.SECONDS);
    }
}
```

### 1.8 ScheduledThreadPoolExecutor Deep Dive

```java
import java.util.concurrent.*;
import java.time.*;

/*
ScheduledThreadPoolExecutor extends ThreadPoolExecutor
- Uses DelayedWorkQueue internally (priority queue sorted by execution time)
- Each task wrapped in ScheduledFutureTask (implements Delayed + RunnableScheduledFuture)
- Core pool size = fixed threads (max is always Integer.MAX_VALUE but unused)

Internal flow for scheduleAtFixedRate(task, 0, 1sec):
1. Wrap task in ScheduledFutureTask with triggerTime = now + 0
2. Add to DelayedWorkQueue (sorted by triggerTime)
3. Worker thread polls queue → blocks until triggerTime reached
4. Execute task
5. After execution: set next triggerTime = triggerTime + period
6. Re-add ScheduledFutureTask to queue with new triggerTime
7. Repeat from step 3
*/

public class ScheduledExecutorDeepDive {
    public static void main(String[] args) throws Exception {

        ScheduledThreadPoolExecutor scheduler = new ScheduledThreadPoolExecutor(2);

        // ==================== schedule(): one-shot delay ====================
        System.out.println("Scheduling one-shot task...");
        ScheduledFuture<String> future = scheduler.schedule(
            () -> "Hello from delayed task!",  // Callable
            2,                                  // delay
            TimeUnit.SECONDS                    // unit
        );
        System.out.println("Result: " + future.get());  // blocks for 2s, then prints
        System.out.println("Remaining delay: " + future.getDelay(TimeUnit.MILLISECONDS) + "ms");

        // ==================== scheduleAtFixedRate(): periodic, fixed interval ====================
        /*
        Timeline (period = 1 second):
        |--task(200ms)--|--------wait 800ms--------|--task(200ms)--|--wait 800ms--|
        t=0            t=0.2                       t=1            t=1.2         t=2

        If task takes LONGER than period:
        |--task(1500ms)------|--task(1500ms)------|
        t=0                  t=1.5               t=3.0
        (next execution starts immediately after previous finishes, never concurrent)
        */
        System.out.println("\n--- scheduleAtFixedRate ---");
        ScheduledFuture<?> fixedRate = scheduler.scheduleAtFixedRate(
            () -> {
                System.out.println("[FixedRate] " + LocalTime.now() +
                    " Thread: " + Thread.currentThread().getName());
                try { Thread.sleep(200); } catch (InterruptedException e) {}
            },
            0,    // initialDelay
            1,    // period (time between START of consecutive executions)
            TimeUnit.SECONDS
        );

        Thread.sleep(3500);
        fixedRate.cancel(false);

        // ==================== scheduleWithFixedDelay(): fixed gap between end and start ====================
        /*
        Timeline (delay = 1 second, task takes 200ms):
        |--task(200ms)--|------delay 1000ms------|--task(200ms)--|------delay 1000ms------|
        t=0            t=0.2                     t=1.2          t=1.4                    t=2.4

        Gap is always 1 second AFTER task completes (regardless of task duration)
        */
        System.out.println("\n--- scheduleWithFixedDelay ---");
        ScheduledFuture<?> fixedDelay = scheduler.scheduleWithFixedDelay(
            () -> {
                System.out.println("[FixedDelay] " + LocalTime.now());
                try { Thread.sleep(200); } catch (InterruptedException e) {}
            },
            0,    // initialDelay
            1,    // delay (time between END of previous and START of next)
            TimeUnit.SECONDS
        );

        Thread.sleep(3500);
        fixedDelay.cancel(false);

        // ==================== Configuration options ====================

        // Continue periodic tasks after shutdown?
        scheduler.setContinueExistingPeriodicTasksAfterShutdownPolicy(false); // default: false
        // Execute delayed tasks after shutdown?
        scheduler.setExecuteExistingDelayedTasksAfterShutdownPolicy(true);    // default: true
        // Remove cancelled tasks from queue immediately?
        scheduler.setRemoveOnCancelPolicy(true);  // default: false (saves queue restructuring)

        scheduler.shutdown();
        scheduler.awaitTermination(5, TimeUnit.SECONDS);
    }
}
```

### 1.9 Custom Thread Pool From Scratch (Interview Implementation)

```java
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Simplified ThreadPool implementation — demonstrates core concepts.
 * Interview-ready: shows understanding of worker threads, task queue, and shutdown.
 */
public class SimpleThreadPool {
    private final int poolSize;
    private final BlockingQueue<Runnable> taskQueue;
    private final Thread[] workers;
    private volatile boolean isShutdown = false;
    private final AtomicInteger completedTasks = new AtomicInteger(0);

    public SimpleThreadPool(int poolSize, int queueCapacity) {
        this.poolSize = poolSize;
        this.taskQueue = new ArrayBlockingQueue<>(queueCapacity);
        this.workers = new Thread[poolSize];

        // Create and start worker threads
        for (int i = 0; i < poolSize; i++) {
            workers[i] = new Thread(new Worker(), "Pool-Worker-" + i);
            workers[i].start();
        }
    }

    /**
     * Submit a task for execution.
     * Blocks if queue is full (bounded back-pressure).
     */
    public void execute(Runnable task) {
        if (isShutdown) {
            throw new RejectedExecutionException("ThreadPool is shut down");
        }
        try {
            taskQueue.put(task); // blocks if queue is full
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * Graceful shutdown: stop accepting new tasks, finish existing.
     */
    public void shutdown() {
        isShutdown = true;
    }

    /**
     * Forceful shutdown: interrupt all workers.
     */
    public void shutdownNow() {
        isShutdown = true;
        for (Thread worker : workers) {
            worker.interrupt();
        }
    }

    /**
     * Wait for all workers to finish.
     */
    public void awaitTermination(long timeout, TimeUnit unit) throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        for (Thread worker : workers) {
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) break;
            worker.join(unit.toMillis(timeout));
        }
    }

    public int getCompletedTaskCount() {
        return completedTasks.get();
    }

    public int getQueueSize() {
        return taskQueue.size();
    }

    /**
     * Worker thread: continuously takes tasks from queue and executes them.
     */
    private class Worker implements Runnable {
        @Override
        public void run() {
            while (!isShutdown || !taskQueue.isEmpty()) {
                try {
                    // poll with timeout so we can check isShutdown periodically
                    Runnable task = taskQueue.poll(100, TimeUnit.MILLISECONDS);
                    if (task != null) {
                        try {
                            task.run();
                            completedTasks.incrementAndGet();
                        } catch (Exception e) {
                            System.err.println(Thread.currentThread().getName()
                                + " task failed: " + e.getMessage());
                        }
                    }
                } catch (InterruptedException e) {
                    // shutdownNow() was called
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            System.out.println(Thread.currentThread().getName() + " terminated");
        }
    }

    // Demo
    public static void main(String[] args) throws InterruptedException {
        SimpleThreadPool pool = new SimpleThreadPool(3, 10);

        // Submit 10 tasks
        for (int i = 1; i <= 10; i++) {
            final int taskId = i;
            pool.execute(() -> {
                System.out.println("Task " + taskId + " running on "
                    + Thread.currentThread().getName());
                try { Thread.sleep(500); } catch (InterruptedException e) {}
            });
        }

        Thread.sleep(2000);
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("Completed tasks: " + pool.getCompletedTaskCount());
    }
}
```

### 1.10 Thread Pool Sizing Strategies

```java
/*
┌─────────────────────────────────────────────────────────────────────┐
│                    THREAD POOL SIZING GUIDE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CPU-BOUND tasks (computation, sorting, parsing):                   │
│  ─────────────────────────────────────────────────                  │
│  Optimal threads = Number of CPU cores (N)                          │
│  Or: N + 1 (to keep CPU busy during page faults)                   │
│                                                                     │
│  int cores = Runtime.getRuntime().availableProcessors();            │
│  ExecutorService pool = Executors.newFixedThreadPool(cores + 1);    │
│                                                                     │
│  More threads = context switching overhead, no benefit              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  IO-BOUND tasks (HTTP calls, DB queries, file I/O):                 │
│  ───────────────────────────────────────────────────                │
│  Optimal threads = N * (1 + W/C)                                    │
│  Where: N = CPU cores                                               │
│         W = Wait time (time spent waiting for I/O)                  │
│         C = Compute time (time spent computing)                     │
│                                                                     │
│  Example: N=4, task spends 80% waiting, 20% computing              │
│  Threads = 4 * (1 + 0.8/0.2) = 4 * 5 = 20 threads                 │
│                                                                     │
│  Rule of thumb for heavy I/O: 2 * N to 10 * N                      │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  MIXED workloads:                                                   │
│  ─────────────────                                                  │
│  Use separate pools for CPU-bound and IO-bound tasks!               │
│  Don't let IO tasks starve CPU tasks (or vice versa)                │
│                                                                     │
│  ExecutorService cpuPool = Executors.newFixedThreadPool(cores);     │
│  ExecutorService ioPool = Executors.newFixedThreadPool(cores * 5);  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
*/

public class ThreadPoolSizingDemo {
    public static void main(String[] args) {
        int cores = Runtime.getRuntime().availableProcessors();
        System.out.println("Available cores: " + cores);
        
        // CPU-bound pool
        ExecutorService cpuPool = Executors.newFixedThreadPool(cores + 1);
        
        // IO-bound pool (assuming 80% wait time)
        int ioPoolSize = cores * (1 + 80/20); // = cores * 5
        ExecutorService ioPool = Executors.newFixedThreadPool(ioPoolSize);
        
        System.out.println("CPU pool size: " + (cores + 1));
        System.out.println("IO pool size: " + ioPoolSize);
        
        cpuPool.shutdown();
        ioPool.shutdown();
    }
}
```

---

## 2. Future and Callable

### 2.1 Callable vs Runnable

```java
import java.util.concurrent.*;

public class CallableVsRunnable {
    
    // Runnable: no return value, no checked exceptions
    Runnable runnable = () -> {
        System.out.println("Running task");
        // Cannot return a value
        // Cannot throw checked exceptions
    };
    
    // Callable: returns value, can throw checked exceptions
    Callable<Integer> callable = () -> {
        Thread.sleep(1000); // Can throw InterruptedException (checked)
        if (Math.random() > 0.5) {
            throw new Exception("Random failure"); // Can throw any exception
        }
        return 42; // Returns a value
    };
    
    public static void main(String[] args) throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(2);
        
        // Submit Callable, get Future
        Future<Integer> future = executor.submit(() -> {
            Thread.sleep(2000);
            return 100;
        });
        
        System.out.println("Task submitted, doing other work...");
        
        // Future methods
        System.out.println("Is done: " + future.isDone());       // false
        System.out.println("Is cancelled: " + future.isCancelled()); // false
        
        Integer result = future.get(); // BLOCKS until result is available
        System.out.println("Result: " + result); // 100
        
        System.out.println("Is done: " + future.isDone());       // true
        
        executor.shutdown();
    }
}
```

### 2.2 Future API

```java
import java.util.concurrent.*;

public class FutureApiDemo {
    
    public static void main(String[] args) {
        ExecutorService executor = Executors.newFixedThreadPool(3);
        
        // ==================== get() - blocks indefinitely ====================
        Future<String> f1 = executor.submit(() -> {
            Thread.sleep(2000);
            return "Task 1 result";
        });
        
        try {
            String result = f1.get(); // Blocks until complete
            System.out.println(result);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (ExecutionException e) {
            System.out.println("Task threw exception: " + e.getCause());
        }
        
        // ==================== get(timeout) - blocks with timeout ====================
        Future<String> f2 = executor.submit(() -> {
            Thread.sleep(5000);
            return "Slow task";
        });
        
        try {
            String result = f2.get(2, TimeUnit.SECONDS); // Wait max 2 seconds
        } catch (TimeoutException e) {
            System.out.println("Task didn't complete in time!");
            f2.cancel(true); // Cancel the slow task
        } catch (InterruptedException | ExecutionException e) {
            e.printStackTrace();
        }
        
        // ==================== cancel() ====================
        Future<String> f3 = executor.submit(() -> {
            while (!Thread.currentThread().isInterrupted()) {
                // Working...
                Thread.sleep(100);
            }
            return "Never reached";
        });
        
        f3.cancel(true);  // true = interrupt if running (mayInterruptIfRunning)
        // cancel(false) = don't interrupt, just prevent from starting if not yet started
        
        System.out.println("Cancelled: " + f3.isCancelled()); // true
        System.out.println("Done: " + f3.isDone());           // true (cancelled counts as done!)
        
        // Calling get() on cancelled future throws CancellationException
        try {
            f3.get();
        } catch (CancellationException e) {
            System.out.println("Cannot get result of cancelled task");
        } catch (InterruptedException | ExecutionException e) {
            e.printStackTrace();
        }
        
        executor.shutdown();
    }
}

/*
LIMITATIONS OF FUTURE:
1. No manual completion - can't complete a Future with a value
2. No chaining - can't chain dependent operations
3. No combining - can't combine multiple Futures
4. No exception handling pipeline - must try/catch
5. Blocking get() - only way to retrieve result blocks the thread
6. No callbacks - can't attach action to run on completion

These limitations are all addressed by CompletableFuture!
*/
```

---

## 3. CompletableFuture (Complete API)

### 3.1 Creation

```java
import java.util.concurrent.*;

public class CompletableFutureCreation {
    
    public static void main(String[] args) throws Exception {
        
        // ==================== supplyAsync - with return value ====================
        CompletableFuture<String> cf1 = CompletableFuture.supplyAsync(() -> {
            System.out.println("Running in: " + Thread.currentThread().getName());
            // Uses ForkJoinPool.commonPool() by default
            return "Hello from supplyAsync";
        });
        System.out.println(cf1.get()); // "Hello from supplyAsync"
        
        // With custom executor
        ExecutorService myPool = Executors.newFixedThreadPool(4);
        CompletableFuture<Integer> cf2 = CompletableFuture.supplyAsync(() -> {
            return 42;
        }, myPool); // Uses our custom pool
        
        // ==================== runAsync - no return value ====================
        CompletableFuture<Void> cf3 = CompletableFuture.runAsync(() -> {
            System.out.println("Fire and forget task");
        });
        cf3.get(); // Returns null (Void)
        
        // ==================== completedFuture - already completed ====================
        CompletableFuture<String> cf4 = CompletableFuture.completedFuture("Already done");
        System.out.println(cf4.get()); // "Already done" - no async computation
        
        // ==================== Manual completion ====================
        CompletableFuture<String> cf5 = new CompletableFuture<>();
        // Some other thread or event completes it later:
        new Thread(() -> {
            try { Thread.sleep(1000); } catch (InterruptedException e) {}
            cf5.complete("Manually completed!"); // Set the result
        }).start();
        System.out.println(cf5.get()); // Blocks until complete is called
        
        // completeExceptionally
        CompletableFuture<String> cf6 = new CompletableFuture<>();
        cf6.completeExceptionally(new RuntimeException("Something went wrong"));
        // cf6.get() would throw ExecutionException wrapping RuntimeException
        
        myPool.shutdown();
    }
}
```

### 3.2 Transform: thenApply, thenAccept, thenRun

```java
import java.util.concurrent.*;

public class CompletableFutureTransform {
    
    public static void main(String[] args) throws Exception {
        
        // ==================== thenApply - transform result (like map) ====================
        // Function<T, U>: takes result, returns new value
        CompletableFuture<String> result = CompletableFuture
            .supplyAsync(() -> "hello")
            .thenApply(s -> s.toUpperCase())      // "HELLO"
            .thenApply(s -> s + " WORLD");        // "HELLO WORLD"
        
        System.out.println(result.get()); // "HELLO WORLD"
        
        // ==================== thenAccept - consume result (no return) ====================
        // Consumer<T>: takes result, returns void
        CompletableFuture<Void> consumed = CompletableFuture
            .supplyAsync(() -> "Hello")
            .thenAccept(s -> System.out.println("Received: " + s)); // Side effect
        // Returns CompletableFuture<Void>
        
        // ==================== thenRun - run action (ignores result) ====================
        // Runnable: no input, no output
        CompletableFuture<Void> ran = CompletableFuture
            .supplyAsync(() -> "Hello")
            .thenRun(() -> System.out.println("Computation finished!"));
        // Doesn't receive the result, just runs after completion
        
        // ==================== Chaining multiple transformations ====================
        CompletableFuture<Double> pipeline = CompletableFuture
            .supplyAsync(() -> "100")             // String
            .thenApply(Integer::parseInt)         // Integer (100)
            .thenApply(n -> n * 2)                // Integer (200)
            .thenApply(n -> n / 3.0);             // Double (66.67)
        
        System.out.println("Pipeline: " + pipeline.get()); // 66.666...
    }
}
```

### 3.3 Compose: thenCompose, thenCombine, allOf, anyOf

```java
import java.util.concurrent.*;
import java.util.stream.*;
import java.util.*;

public class CompletableFutureCompose {
    
    // Simulated async service calls
    static CompletableFuture<String> getUserName(int userId) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(500);
            return "User-" + userId;
        });
    }
    
    static CompletableFuture<String> getEmail(String userName) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(300);
            return userName.toLowerCase() + "@email.com";
        });
    }
    
    static CompletableFuture<Integer> getAge(int userId) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(400);
            return 25 + userId;
        });
    }
    
    public static void main(String[] args) throws Exception {
        
        // ==================== thenCompose - chain dependent futures (flatMap) ====================
        // Used when the next step returns a CompletableFuture
        // Function<T, CompletableFuture<U>>
        
        CompletableFuture<String> email = getUserName(1)
            .thenCompose(name -> getEmail(name)); // Sequential: get user, THEN get email
        
        System.out.println("Email: " + email.get()); // "user-1@email.com"
        
        // thenApply vs thenCompose:
        // thenApply(fn) → if fn returns CompletableFuture, you get CompletableFuture<CompletableFuture<T>> (nested!)
        // thenCompose(fn) → unwraps it to CompletableFuture<T> (like flatMap)
        
        // ==================== thenCombine - combine two independent futures ====================
        // BiFunction<T, U, V>: takes both results, returns combined
        
        CompletableFuture<String> nameFuture = getUserName(1);
        CompletableFuture<Integer> ageFuture = getAge(1);
        
        CompletableFuture<String> combined = nameFuture.thenCombine(
            ageFuture,
            (name, age) -> name + " is " + age + " years old"
        );
        // Both run in PARALLEL, combined when both complete
        System.out.println(combined.get()); // "User-1 is 26 years old"
        
        // ==================== allOf - wait for ALL futures ====================
        // Returns CompletableFuture<Void> - doesn't give you the results directly
        
        CompletableFuture<String> f1 = CompletableFuture.supplyAsync(() -> { sleep(1000); return "A"; });
        CompletableFuture<String> f2 = CompletableFuture.supplyAsync(() -> { sleep(2000); return "B"; });
        CompletableFuture<String> f3 = CompletableFuture.supplyAsync(() -> { sleep(500);  return "C"; });
        
        CompletableFuture<Void> allDone = CompletableFuture.allOf(f1, f2, f3);
        
        // Get all results after allOf completes
        CompletableFuture<List<String>> allResults = allDone.thenApply(v ->
            Stream.of(f1, f2, f3)
                .map(CompletableFuture::join) // join() is like get() but unchecked
                .collect(Collectors.toList())
        );
        
        System.out.println("All results: " + allResults.get()); // [A, B, C]
        
        // ==================== anyOf - first completed future ====================
        // Returns CompletableFuture<Object> - result of fastest future
        
        CompletableFuture<Object> fastest = CompletableFuture.anyOf(f1, f2, f3);
        System.out.println("Fastest: " + fastest.get()); // "C" (500ms is fastest)
        
        // ==================== Practical: Parallel API calls ====================
        List<Integer> userIds = List.of(1, 2, 3, 4, 5);
        
        List<CompletableFuture<String>> futures = userIds.stream()
            .map(id -> getUserName(id))
            .collect(Collectors.toList());
        
        CompletableFuture<List<String>> allNames = CompletableFuture
            .allOf(futures.toArray(new CompletableFuture[0]))
            .thenApply(v -> futures.stream()
                .map(CompletableFuture::join)
                .collect(Collectors.toList()));
        
        System.out.println("All names: " + allNames.get());
    }
    
    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) {}
    }
}
```

### 3.4 Error Handling

```java
import java.util.concurrent.*;

public class CompletableFutureErrorHandling {
    
    public static void main(String[] args) throws Exception {
        
        // ==================== exceptionally - recover from exception ====================
        // Like catch block - provides fallback value
        CompletableFuture<String> recovered = CompletableFuture
            .supplyAsync(() -> {
                if (true) throw new RuntimeException("Oops!");
                return "success";
            })
            .exceptionally(ex -> {
                System.out.println("Error: " + ex.getMessage());
                return "default value"; // Recovery value
            });
        
        System.out.println(recovered.get()); // "default value"
        
        // ==================== handle - handle both success AND failure ====================
        // BiFunction<T, Throwable, U>: receives result (or null) and exception (or null)
        CompletableFuture<String> handled = CompletableFuture
            .supplyAsync(() -> {
                if (Math.random() > 0.5) throw new RuntimeException("Failed!");
                return "success";
            })
            .handle((result, ex) -> {
                if (ex != null) {
                    System.out.println("Handling error: " + ex.getMessage());
                    return "recovered";
                }
                return result.toUpperCase();
            });
        
        System.out.println(handled.get()); // Either "SUCCESS" or "recovered"
        
        // ==================== whenComplete - peek at result/error (doesn't transform) ====================
        // BiConsumer<T, Throwable>: side effects only, doesn't change the result
        CompletableFuture<String> peeked = CompletableFuture
            .supplyAsync(() -> "Hello")
            .whenComplete((result, ex) -> {
                if (ex != null) {
                    System.err.println("Failed with: " + ex);
                } else {
                    System.out.println("Completed with: " + result);
                }
            });
        // Result is still "Hello" - whenComplete doesn't change it
        
        // ==================== Error propagation in chains ====================
        CompletableFuture<String> chain = CompletableFuture
            .supplyAsync(() -> "hello")
            .thenApply(s -> {
                throw new RuntimeException("Error in step 2");
            })
            .thenApply(s -> {
                // This is SKIPPED when previous stage fails
                System.out.println("This won't print");
                return s + " world";
            })
            .exceptionally(ex -> {
                // Catches error from ANY previous stage
                return "Error recovered: " + ex.getMessage();
            });
        
        System.out.println(chain.get()); // "Error recovered: ..."
        
        // ==================== Multiple exception handlers ====================
        CompletableFuture<String> multiHandle = CompletableFuture
            .supplyAsync(() -> {
                throw new IllegalArgumentException("Bad arg");
            })
            .exceptionally(ex -> {
                if (ex.getCause() instanceof IllegalArgumentException) {
                    return "handled IllegalArg";
                }
                throw new CompletionException(ex); // Re-throw
            })
            .thenApply(s -> s + " → processed");
        
        System.out.println(multiHandle.get()); // "handled IllegalArg → processed"
    }
}
```

### 3.5 Async Variants

```java
import java.util.concurrent.*;

public class CompletableFutureAsync {
    
    /*
    Every callback method has THREE variants:
    
    thenApply(fn)       - Runs in SAME thread as previous stage (or caller if already done)
    thenApplyAsync(fn)  - Runs in ForkJoinPool.commonPool()
    thenApplyAsync(fn, executor) - Runs in specified executor
    
    Same pattern for: thenAccept/Async, thenRun/Async, thenCompose/Async,
                      handle/Async, whenComplete/Async, exceptionally/Async (Java 12)
    */
    
    public static void main(String[] args) throws Exception {
        ExecutorService myPool = Executors.newFixedThreadPool(4);
        
        // Non-async: callback MAY run in the same thread as supplier
        CompletableFuture.supplyAsync(() -> {
            System.out.println("Supply: " + Thread.currentThread().getName());
            return "data";
        }).thenApply(s -> {
            // Might run in ForkJoinPool worker or calling thread
            System.out.println("Apply: " + Thread.currentThread().getName());
            return s.toUpperCase();
        }).get();
        
        // Async: callback ALWAYS runs in a pool thread
        CompletableFuture.supplyAsync(() -> {
            System.out.println("Supply: " + Thread.currentThread().getName());
            return "data";
        }).thenApplyAsync(s -> {
            // Always runs in ForkJoinPool.commonPool()
            System.out.println("ApplyAsync: " + Thread.currentThread().getName());
            return s.toUpperCase();
        }).get();
        
        // Async with custom executor
        CompletableFuture.supplyAsync(() -> "data")
            .thenApplyAsync(s -> {
                // Runs in myPool
                System.out.println("Custom pool: " + Thread.currentThread().getName());
                return s.toUpperCase();
            }, myPool)
            .get();
        
        myPool.shutdown();
    }
}
```

### 3.6 Complete Practical Example: Parallel API Calls

```java
import java.util.concurrent.*;
import java.util.*;
import java.util.stream.*;

public class ParallelApiCallsExample {
    
    // Simulated API calls
    static CompletableFuture<String> fetchUserProfile(int userId) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(1000);
            if (userId == 3) throw new RuntimeException("User 3 not found");
            return "{\"id\":" + userId + ",\"name\":\"User" + userId + "\"}";
        });
    }
    
    static CompletableFuture<List<String>> fetchUserOrders(int userId) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(800);
            return List.of("Order-" + userId + "-A", "Order-" + userId + "-B");
        });
    }
    
    static CompletableFuture<Double> fetchUserBalance(int userId) {
        return CompletableFuture.supplyAsync(() -> {
            sleep(600);
            return userId * 100.50;
        });
    }
    
    // Aggregate user data from multiple services in parallel
    static CompletableFuture<Map<String, Object>> fetchCompleteUserData(int userId) {
        CompletableFuture<String> profileFuture = fetchUserProfile(userId);
        CompletableFuture<List<String>> ordersFuture = fetchUserOrders(userId);
        CompletableFuture<Double> balanceFuture = fetchUserBalance(userId);
        
        // All three API calls happen IN PARALLEL
        return CompletableFuture.allOf(profileFuture, ordersFuture, balanceFuture)
            .thenApply(v -> {
                Map<String, Object> userData = new HashMap<>();
                userData.put("profile", profileFuture.join());
                userData.put("orders", ordersFuture.join());
                userData.put("balance", balanceFuture.join());
                return userData;
            })
            .exceptionally(ex -> {
                System.err.println("Error fetching user data: " + ex.getMessage());
                return Map.of("error", ex.getMessage());
            });
    }
    
    // Fetch multiple users in parallel with timeout and error handling
    static CompletableFuture<List<Map<String, Object>>> fetchMultipleUsers(List<Integer> userIds) {
        List<CompletableFuture<Map<String, Object>>> futures = userIds.stream()
            .map(id -> fetchCompleteUserData(id)
                .orTimeout(3, TimeUnit.SECONDS)           // Java 9: timeout per user
                .exceptionally(ex -> Map.of(
                    "userId", id,
                    "error", ex.getMessage()
                )))
            .collect(Collectors.toList());
        
        return CompletableFuture.allOf(futures.toArray(new CompletableFuture[0]))
            .thenApply(v -> futures.stream()
                .map(CompletableFuture::join)
                .collect(Collectors.toList()));
    }
    
    public static void main(String[] args) throws Exception {
        long start = System.currentTimeMillis();
        
        // Fetch data for multiple users in parallel
        List<Integer> userIds = List.of(1, 2, 3, 4, 5);
        List<Map<String, Object>> results = fetchMultipleUsers(userIds).get();
        
        results.forEach(r -> System.out.println(r));
        
        long elapsed = System.currentTimeMillis() - start;
        System.out.println("\nTotal time: " + elapsed + "ms");
        // Sequential would be: 5 * (1000 + 800 + 600) = 12000ms
        // Parallel: ~1000ms (limited by slowest single call)
    }
    
    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) {}
    }
}

/*
OUTPUT:
{profile={"id":1,"name":"User1"}, orders=[Order-1-A, Order-1-B], balance=100.5}
{profile={"id":2,"name":"User2"}, orders=[Order-2-A, Order-2-B], balance=201.0}
{userId=3, error=java.lang.RuntimeException: User 3 not found}
{profile={"id":4,"name":"User4"}, orders=[Order-4-A, Order-4-B], balance=402.0}
{profile={"id":5,"name":"User5"}, orders=[Order-5-A, Order-5-B], balance=502.5}

Total time: ~1050ms (instead of 12000ms sequential!)
*/
```

---

## 4. Concurrent Collections

### 4.1 ConcurrentHashMap

```java
import java.util.concurrent.*;
import java.util.*;

public class ConcurrentHashMapDemo {
    
    public static void main(String[] args) throws InterruptedException {
        ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
        
        // Basic thread-safe operations
        map.put("apple", 1);
        map.putIfAbsent("banana", 2);    // Only if key not present
        map.replace("apple", 1, 10);     // CAS: replace if current value is 1
        map.remove("banana", 2);         // Remove if value is 2
        
        // ==================== compute - atomically update ====================
        map.put("counter", 0);
        
        // Atomic read-modify-write
        map.compute("counter", (key, val) -> val + 1);  // counter = 1
        map.compute("counter", (key, val) -> val + 1);  // counter = 2
        
        // computeIfAbsent - compute only if key missing (lazy init)
        map.computeIfAbsent("newKey", key -> key.length()); // "newKey" → 6
        
        // computeIfPresent - compute only if key exists
        map.computeIfPresent("counter", (key, val) -> val * 2); // counter = 4
        
        // ==================== merge - combine values ====================
        map.put("score", 10);
        map.merge("score", 5, Integer::sum);  // 10 + 5 = 15
        map.merge("score", 3, Integer::sum);  // 15 + 3 = 18
        // merge("newKey", value, fn): if key absent, just put value
        map.merge("absent", 100, Integer::sum); // absent → 100
        
        // ==================== Bulk operations (parallel, Java 8) ====================
        ConcurrentHashMap<String, Integer> prices = new ConcurrentHashMap<>();
        prices.put("Apple", 150);
        prices.put("Banana", 50);
        prices.put("Cherry", 200);
        prices.put("Date", 300);
        
        // forEach - parallel iteration
        // parallelismThreshold: if map size > threshold, parallelize
        prices.forEach(2, (key, value) -> {  // threshold=2 → parallel if >2 entries
            System.out.println(key + " = " + value);
        });
        
        // search - find first matching entry (returns null or result)
        String expensive = prices.search(1, (key, value) -> {
            return value > 250 ? key : null;
        });
        System.out.println("Expensive: " + expensive); // "Date"
        
        // reduce - aggregate all values
        Integer total = prices.reduce(1,
            (key, value) -> value,     // transform: extract value
            Integer::sum               // reduce: sum all values
        );
        System.out.println("Total: " + total); // 700
        
        // reduceValues - simpler reduce on values only
        Integer max = prices.reduceValues(1, Integer::max);
        System.out.println("Max price: " + max); // 300
        
        // ==================== Thread-safe word counter ====================
        ConcurrentHashMap<String, Long> wordCount = new ConcurrentHashMap<>();
        String[] words = {"hello", "world", "hello", "java", "world", "hello"};
        
        // Multiple threads can safely count
        ExecutorService pool = Executors.newFixedThreadPool(4);
        for (String word : words) {
            pool.submit(() -> wordCount.merge(word, 1L, Long::sum));
        }
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        
        System.out.println("Word counts: " + wordCount);
        // {hello=3, world=2, java=1}
    }
}

/*
ConcurrentHashMap vs Collections.synchronizedMap vs Hashtable:

ConcurrentHashMap:
- Lock striping (segments) - multiple threads can write simultaneously to different segments
- No locking for reads (volatile reads)
- Weakly consistent iterators (don't throw ConcurrentModificationException)
- Null keys/values NOT allowed
- Best performance for concurrent access

synchronizedMap:
- Single lock for entire map
- Iterators MUST be externally synchronized
- Allows null key (one) and null values
- Poor concurrent performance

Hashtable:
- Same as synchronizedMap (single lock)
- Legacy, don't use
- No null keys or values
*/
```

### 4.2 CopyOnWriteArrayList & CopyOnWriteArraySet

```java
import java.util.concurrent.*;
import java.util.*;

public class CopyOnWriteDemo {
    
    /*
    CopyOnWriteArrayList:
    - Every WRITE creates a new copy of the entire array
    - READs are lock-free (snapshot semantics)
    - Ideal when reads >> writes
    - Iterator never throws ConcurrentModificationException
    - Uses: event listener lists, caches that rarely change
    */
    
    public static void main(String[] args) {
        CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>();
        list.add("A");
        list.add("B");
        list.add("C");
        
        // Safe iteration even while modifying
        new Thread(() -> {
            for (String s : list) {
                System.out.println("Reading: " + s);
                try { Thread.sleep(100); } catch (InterruptedException e) {}
            }
            // Iterator sees snapshot at time of creation
        }).start();
        
        new Thread(() -> {
            list.add("D"); // Creates new internal array copy
            list.set(0, "X"); // Creates new internal array copy
            System.out.println("Modified list: " + list);
        }).start();
        
        // CopyOnWriteArraySet - Set backed by CopyOnWriteArrayList
        CopyOnWriteArraySet<String> set = new CopyOnWriteArraySet<>();
        set.add("X");
        set.add("Y");
        set.add("X"); // Duplicate - not added
        System.out.println("Set: " + set); // [X, Y]
    }
}

/*
PERFORMANCE CHARACTERISTICS:
- add():     O(n) - copies entire array
- get():     O(1) - direct array access
- contains(): O(n) - linear scan
- iterator(): O(1) - returns snapshot

DO use when: reads vastly outnumber writes, small collections, iteration-heavy
DON'T use when: frequent writes, large collections (copying is expensive)
*/
```

### 4.3 ConcurrentLinkedQueue & ConcurrentLinkedDeque

```java
import java.util.concurrent.*;

public class ConcurrentQueueDemo {
    
    public static void main(String[] args) throws InterruptedException {
        
        // ==================== ConcurrentLinkedQueue (non-blocking) ====================
        // Lock-free using CAS operations
        // Unbounded queue
        ConcurrentLinkedQueue<String> queue = new ConcurrentLinkedQueue<>();
        
        queue.offer("A");  // Add to tail
        queue.offer("B");
        queue.offer("C");
        
        String head = queue.poll();   // Remove from head (null if empty)
        String peek = queue.peek();   // Look at head without removing
        
        System.out.println("Polled: " + head);  // A
        System.out.println("Peek: " + peek);    // B
        System.out.println("Size: " + queue.size()); // 2 (Note: size() is O(n)!)
        
        // ==================== ConcurrentLinkedDeque (double-ended) ====================
        ConcurrentLinkedDeque<String> deque = new ConcurrentLinkedDeque<>();
        
        deque.offerFirst("B");  // Add to front
        deque.offerLast("C");   // Add to back
        deque.offerFirst("A");  // Add to front
        
        System.out.println("First: " + deque.pollFirst()); // A
        System.out.println("Last: " + deque.pollLast());   // C
    }
}
```

### 4.4 BlockingQueue Implementations

```java
import java.util.concurrent.*;

public class BlockingQueueDemo {
    
    public static void main(String[] args) throws InterruptedException {
        
        // ==================== ArrayBlockingQueue (bounded, fixed array) ====================
        BlockingQueue<String> arrayBQ = new ArrayBlockingQueue<>(3); // capacity=3
        arrayBQ.put("A");  // Blocks if full
        arrayBQ.put("B");
        arrayBQ.put("C");
        // arrayBQ.put("D"); // Would BLOCK here (queue full)
        
        String item = arrayBQ.take(); // Blocks if empty
        System.out.println("Took: " + item); // A
        
        // ==================== LinkedBlockingQueue (optionally bounded) ====================
        BlockingQueue<String> linkedBQ = new LinkedBlockingQueue<>(100); // bounded
        BlockingQueue<String> unboundedBQ = new LinkedBlockingQueue<>(); // Integer.MAX_VALUE
        
        // ==================== PriorityBlockingQueue (unbounded, sorted) ====================
        BlockingQueue<Integer> priorityBQ = new PriorityBlockingQueue<>();
        priorityBQ.put(5);
        priorityBQ.put(1);
        priorityBQ.put(3);
        System.out.println(priorityBQ.take()); // 1 (smallest first)
        System.out.println(priorityBQ.take()); // 3
        System.out.println(priorityBQ.take()); // 5
        
        // ==================== SynchronousQueue (zero capacity) ====================
        // Each put() blocks until another thread calls take() (hand-off)
        BlockingQueue<String> syncQ = new SynchronousQueue<>();
        new Thread(() -> {
            try {
                syncQ.put("handoff"); // Blocks until someone takes
                System.out.println("Handed off!");
            } catch (InterruptedException e) {}
        }).start();
        
        Thread.sleep(1000);
        System.out.println("Received: " + syncQ.take()); // "handoff"
        
        // ==================== DelayQueue (elements available after delay) ====================
        BlockingQueue<DelayedTask> delayQ = new DelayQueue<>();
        delayQ.put(new DelayedTask("Task-3s", 3000));
        delayQ.put(new DelayedTask("Task-1s", 1000));
        delayQ.put(new DelayedTask("Task-2s", 2000));
        
        // Elements become available in delay order
        System.out.println(delayQ.take()); // Task-1s (after 1 second)
        System.out.println(delayQ.take()); // Task-2s (after 2 seconds)
        System.out.println(delayQ.take()); // Task-3s (after 3 seconds)
    }
}

// DelayQueue requires Delayed interface
class DelayedTask implements Delayed {
    private final String name;
    private final long triggerTime;
    
    public DelayedTask(String name, long delayMs) {
        this.name = name;
        this.triggerTime = System.currentTimeMillis() + delayMs;
    }
    
    @Override
    public long getDelay(TimeUnit unit) {
        long diff = triggerTime - System.currentTimeMillis();
        return unit.convert(diff, TimeUnit.MILLISECONDS);
    }
    
    @Override
    public int compareTo(Delayed other) {
        return Long.compare(this.getDelay(TimeUnit.MILLISECONDS),
                           other.getDelay(TimeUnit.MILLISECONDS));
    }
    
    @Override
    public String toString() { return name; }
}
```

### 4.5 ConcurrentSkipListMap & ConcurrentSkipListSet

```java
import java.util.concurrent.*;
import java.util.*;

/*
ConcurrentSkipListMap = thread-safe TreeMap (sorted, navigable)
- Based on Skip List data structure (not a balanced tree)
- O(log n) for get, put, remove, containsKey
- Lock-free reads, fine-grained locking for writes
- Supports NavigableMap operations (headMap, tailMap, subMap, floorKey, ceilingKey)
- No null keys or values

When to use:
- Need concurrent sorted map
- Need range queries (subMap, headMap, tailMap) under concurrency
- Need floor/ceiling/higher/lower operations thread-safely
*/

public class ConcurrentSkipListDemo {
    public static void main(String[] args) {

        // ==================== ConcurrentSkipListMap ====================
        ConcurrentSkipListMap<Integer, String> map = new ConcurrentSkipListMap<>();
        map.put(5, "five");
        map.put(3, "three");
        map.put(8, "eight");
        map.put(1, "one");
        map.put(7, "seven");

        // Sorted iteration (always in key order)
        System.out.println("Map: " + map); // {1=one, 3=three, 5=five, 7=seven, 8=eight}

        // NavigableMap operations (all thread-safe)
        System.out.println("First key: " + map.firstKey());           // 1
        System.out.println("Last key: " + map.lastKey());             // 8
        System.out.println("Floor(4): " + map.floorKey(4));           // 3 (≤ 4)
        System.out.println("Ceiling(4): " + map.ceilingKey(4));       // 5 (≥ 4)
        System.out.println("Lower(5): " + map.lowerKey(5));           // 3 (< 5)
        System.out.println("Higher(5): " + map.higherKey(5));         // 7 (> 5)

        // Sub-views (thread-safe, live views)
        NavigableMap<Integer, String> sub = map.subMap(3, true, 7, true);
        System.out.println("SubMap[3,7]: " + sub); // {3=three, 5=five, 7=seven}

        NavigableMap<Integer, String> head = map.headMap(5, false);
        System.out.println("HeadMap(<5): " + head); // {1=one, 3=three}

        NavigableMap<Integer, String> tail = map.tailMap(5, true);
        System.out.println("TailMap(>=5): " + tail); // {5=five, 7=seven, 8=eight}

        // Descending order
        NavigableMap<Integer, String> desc = map.descendingMap();
        System.out.println("Descending: " + desc); // {8=eight, 7=seven, 5=five, 3=three, 1=one}

        // Atomic compute operations
        map.computeIfAbsent(10, k -> "ten");
        map.merge(5, "-updated", String::concat); // "five-updated"

        // Poll (remove) first/last
        Map.Entry<Integer, String> first = map.pollFirstEntry(); // removes {1, "one"}
        Map.Entry<Integer, String> last = map.pollLastEntry();   // removes {10, "ten"}

        // ==================== ConcurrentSkipListSet ====================
        // Thread-safe TreeSet — backed by ConcurrentSkipListMap
        ConcurrentSkipListSet<String> set = new ConcurrentSkipListSet<>();
        set.add("banana");
        set.add("apple");
        set.add("cherry");
        set.add("date");

        System.out.println("\nSet: " + set); // [apple, banana, cherry, date] (sorted)
        System.out.println("First: " + set.first());           // apple
        System.out.println("Last: " + set.last());             // date
        System.out.println("Floor(c): " + set.floor("c"));     // cherry
        System.out.println("Ceiling(c): " + set.ceiling("c")); // cherry
        System.out.println("HeadSet(<cherry): " + set.headSet("cherry")); // [apple, banana]

        // Thread-safe range iteration
        for (String s : set.subSet("banana", true, "date", true)) {
            System.out.println("Range: " + s);
        }
    }
}

/*
SKIP LIST INTERNALS:
┌─────────────────────────────────────────────────────────────────┐
│ Level 3: HEAD ─────────────────────────────── 7 ─────── NIL    │
│ Level 2: HEAD ──── 3 ──────────────────────── 7 ─────── NIL    │
│ Level 1: HEAD ──── 3 ──── 5 ────────── 7 ──── 8 ────── NIL    │
│ Level 0: HEAD ─ 1 ─ 3 ─ 5 ─ 6 ─ 7 ─ 8 ─ 9 ─ NIL (linked)    │
└─────────────────────────────────────────────────────────────────┘

- Probabilistic data structure (randomized levels)
- Search: start at top level, move right until overshoot, drop down
- Average O(log n) for search/insert/delete
- No rebalancing needed (unlike Red-Black trees)
- Easy to make concurrent (CAS on next pointers)
*/
```

### 4.6 LinkedTransferQueue

```java
import java.util.concurrent.*;

/*
LinkedTransferQueue — most versatile concurrent queue:
- Combines LinkedBlockingQueue + SynchronousQueue behaviors
- Unbounded, non-blocking for producers by default
- transfer() method: blocks until a consumer takes the item (hand-off)
- tryTransfer(): non-blocking hand-off attempt

Methods:
- offer(e) / add(e) — enqueue, never blocks (unbounded)
- put(e) — same as offer (never blocks since unbounded)
- transfer(e) — enqueue, but BLOCK until consumer takes it
- tryTransfer(e) — hand-off immediately if consumer waiting, else false
- tryTransfer(e, timeout, unit) — try hand-off with timeout
- take() — dequeue, blocks if empty
- poll() — dequeue, null if empty
- hasWaitingConsumer() — is there a consumer blocked on take()?
- getWaitingConsumerCount() — how many consumers waiting?
*/

public class LinkedTransferQueueDemo {
    public static void main(String[] args) throws InterruptedException {

        LinkedTransferQueue<String> queue = new LinkedTransferQueue<>();

        // Producer thread using transfer (blocks until consumed)
        Thread producer = new Thread(() -> {
            try {
                System.out.println("Producer: about to transfer 'message'...");
                queue.transfer("message"); // blocks until consumer takes it
                System.out.println("Producer: message was consumed!");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        // Consumer thread
        Thread consumer = new Thread(() -> {
            try {
                Thread.sleep(2000); // simulate delay
                System.out.println("Consumer: taking...");
                String msg = queue.take();
                System.out.println("Consumer: got '" + msg + "'");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();
        // Output:
        // Producer: about to transfer 'message'...
        // (2 second pause)
        // Consumer: taking...
        // Consumer: got 'message'
        // Producer: message was consumed!

        // tryTransfer — non-blocking attempt
        boolean transferred = queue.tryTransfer("data");
        System.out.println("tryTransfer result: " + transferred); // false (no consumer waiting)

        // Regular offer works like LinkedBlockingQueue (never blocks)
        queue.offer("buffered");
        System.out.println("Queue size: " + queue.size()); // 1

        /*
        USE CASES:
        1. Message passing with guaranteed delivery (transfer)
        2. Adaptive: tryTransfer for fast path, offer for fallback
        3. Better performance than SynchronousQueue when buffering is acceptable
        4. Used internally by ForkJoinPool for work stealing
        */
    }
}
```

### 4.7 LinkedBlockingDeque

```java
import java.util.concurrent.*;

/*
LinkedBlockingDeque — thread-safe double-ended blocking queue
- Bounded or unbounded
- All operations on both ends: First and Last
- Implements BlockingDeque<E> (extends BlockingQueue + Deque)
- Single ReentrantLock (less concurrent than ConcurrentLinkedDeque)
- Use when: you need blocking behavior + deque operations

Use cases:
- Work-stealing algorithms (steal from tail, process from head)
- Undo stacks in concurrent apps
- Bounded task buffers with priority at both ends
*/

public class LinkedBlockingDequeDemo {
    public static void main(String[] args) throws InterruptedException {

        // Bounded deque (capacity 5)
        LinkedBlockingDeque<String> deque = new LinkedBlockingDeque<>(5);

        // ==================== Non-blocking operations ====================
        deque.offerFirst("B");     // true (add to front)
        deque.offerLast("C");      // true (add to back)
        deque.offerFirst("A");     // true (add to front)
        System.out.println(deque); // [A, B, C]

        String first = deque.pollFirst();  // "A" (remove from front)
        String last = deque.pollLast();    // "C" (remove from back)
        System.out.println("First: " + first + ", Last: " + last);

        // Peek without removing
        deque.offerFirst("X");
        deque.offerLast("Z");
        System.out.println("Peek first: " + deque.peekFirst()); // X
        System.out.println("Peek last: " + deque.peekLast());   // Z

        // ==================== Blocking operations ====================
        // putFirst / putLast — block if full
        deque.putFirst("Head");
        deque.putLast("Tail");

        // takeFirst / takeLast — block if empty
        String took = deque.takeFirst(); // "Head"
        System.out.println("Took: " + took);

        // ==================== Timed operations ====================
        boolean added = deque.offerFirst("Timed", 1, TimeUnit.SECONDS); // waits up to 1s
        String polled = deque.pollLast(1, TimeUnit.SECONDS);            // waits up to 1s

        // ==================== Use as stack (LIFO) ====================
        deque.clear();
        deque.push("first");   // same as offerFirst
        deque.push("second");
        deque.push("third");
        System.out.println("Pop: " + deque.pop()); // "third" (LIFO)
    }
}
```

### 4.8 ConcurrentHashMap Internals (Java 8+)

```java
/*
┌──────────────────────────────────────────────────────────────────────────┐
│           ConcurrentHashMap Internal Structure (Java 8+)                   │
│                                                                           │
│  Before Java 8: Segment-based (16 segments, each a mini HashMap)         │
│  Java 8+: Lock-per-bucket (CAS + synchronized on first node)             │
│                                                                           │
│  Array of Node (similar to HashMap):                                      │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐              │
│  │ null │Node→ │ null │Node→ │ null │Tree  │ null │Node→ │  (Node[])    │
│  │      │Node→ │      │Node  │      │Root  │      │      │              │
│  │      │Node  │      │      │      │ / \  │      │      │              │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘              │
│    [0]    [1]    [2]    [3]    [4]    [5]    [6]    [7]                  │
│                                                                           │
│  When bucket has ≥ 8 entries (TREEIFY_THRESHOLD):                        │
│    Linked list → Red-Black Tree (O(n) → O(log n) lookup)                 │
│  When bucket drops to ≤ 6 entries (UNTREEIFY_THRESHOLD):                 │
│    Tree → Linked list (simpler structure)                                 │
│                                                                           │
│  CONCURRENCY MODEL:                                                       │
│  ─────────────────                                                        │
│  READ:  No locking! Volatile reads of Node.val and Node.next             │
│         Nodes are never mutated (new Node on update for visibility)       │
│                                                                           │
│  WRITE: CAS on empty bucket (first insert)                                │
│         synchronized(first_node_of_bucket) for existing bucket            │
│         Only locks ONE bucket — other buckets are unaffected!             │
│                                                                           │
│  RESIZE: Concurrent! Multiple threads help with transfer                  │
│          transferIndex tracks progress, threads claim ranges              │
│                                                                           │
│  SIZE:  Not O(1)! Uses CounterCell[] (similar to LongAdder)              │
│         mappingCount() preferred over size() (returns long)               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
*/

import java.util.concurrent.*;
import java.util.*;

public class ConcurrentHashMapInternals {
    public static void main(String[] args) {

        ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();

        // Initial capacity: 16, load factor: 0.75 (resize at 12 entries)
        // ConcurrentHashMap(int initialCapacity, float loadFactor, int concurrencyLevel)
        ConcurrentHashMap<String, Integer> tuned = new ConcurrentHashMap<>(
            256,    // initial capacity (rounded to power of 2)
            0.75f,  // load factor
            16      // concurrency level (hint for internal sizing, less relevant in Java 8+)
        );

        // ==================== Key methods unique to ConcurrentHashMap ====================

        // 1. mappingCount() — returns long (use instead of size() for large maps)
        long count = map.mappingCount(); // more accurate than size() which returns int

        // 2. newKeySet() — concurrent Set backed by ConcurrentHashMap
        Set<String> concurrentSet = ConcurrentHashMap.<String>newKeySet();
        concurrentSet.add("A");
        concurrentSet.add("B");
        // Thread-safe Set without needing Collections.synchronizedSet()

        // 3. keySet(defaultValue) — Set view where add() inserts with default value
        ConcurrentHashMap<String, Boolean> map2 = new ConcurrentHashMap<>();
        Set<String> keySetView = map2.keySet(Boolean.TRUE);
        keySetView.add("X"); // map2 now has {"X" → true}

        // 4. Atomic compute operations (key difference from synchronized HashMap)
        map.put("counter", 0);

        // compute: guaranteed atomic read-modify-write
        map.compute("counter", (k, v) -> v + 1);
        // The function runs while holding the bucket lock → truly atomic

        // computeIfAbsent: lazy initialization pattern (thread-safe!)
        map.computeIfAbsent("cache", k -> expensiveComputation(k));
        // Only ONE thread will execute the function, others wait

        // CAUTION: Don't do recursive computeIfAbsent on same map (deadlock!)
        // map.computeIfAbsent("a", k -> map.computeIfAbsent("b", ...)); // DEADLOCK!

        // ==================== Weakly consistent iterators ====================
        // Iterators reflect state at SOME point during or after construction
        // Never throw ConcurrentModificationException
        // May or may not reflect concurrent modifications
        for (Map.Entry<String, Integer> entry : map.entrySet()) {
            // Safe even if other threads are modifying the map
            System.out.println(entry.getKey() + "=" + entry.getValue());
        }

        // ==================== Null not allowed ====================
        // map.put("key", null);   // NullPointerException!
        // map.put(null, 1);       // NullPointerException!
        // Reason: null return from get() would be ambiguous (absent vs null value)
    }

    private static Integer expensiveComputation(String key) {
        return key.length();
    }
}

/*
COMPARISON: ConcurrentHashMap vs synchronizedMap vs Hashtable

┌─────────────────────┬────────────────────────┬────────────────────┬──────────────┐
│                     │ ConcurrentHashMap      │ synchronizedMap     │ Hashtable    │
├─────────────────────┼────────────────────────┼────────────────────┼──────────────┤
│ Locking             │ Per-bucket (CAS+sync)  │ Entire map          │ Entire map   │
│ Read concurrency    │ Lock-free (volatile)   │ Blocked by writes   │ Blocked      │
│ Write concurrency   │ Multiple buckets       │ Single writer        │ Single       │
│ Iterator            │ Weakly consistent      │ Fail-fast (requires │ Fail-fast    │
│                     │ (no CME)               │  external sync)     │              │
│ Null keys           │ NOT allowed            │ 1 null key allowed  │ NOT allowed  │
│ Null values         │ NOT allowed            │ Allowed             │ NOT allowed  │
│ Atomic compute      │ compute/merge/etc      │ Not available        │ Not available│
│ Bulk parallel ops   │ forEach/search/reduce  │ Not available        │ Not available│
│ Performance         │ Best (high concurrency)│ Poor (global lock)  │ Poor         │
│ When to use         │ High-concurrency maps  │ Need null support    │ Never (legacy)│
└─────────────────────┴────────────────────────┴────────────────────┴──────────────┘
*/
```

### 4.9 Concurrent Collections Summary

```java
/*
┌───────────────────────────────────────────────────────────────────────────────────┐
│                    CONCURRENT COLLECTIONS — DECISION GUIDE                          │
├───────────────────────────────┬────────────────────────────────────────────────────┤
│ Need                          │ Use                                                 │
├───────────────────────────────┼────────────────────────────────────────────────────┤
│ Thread-safe Map               │ ConcurrentHashMap                                   │
│ Thread-safe sorted Map        │ ConcurrentSkipListMap                               │
│ Thread-safe Set               │ ConcurrentHashMap.newKeySet()                       │
│ Thread-safe sorted Set        │ ConcurrentSkipListSet                               │
│ List: reads >> writes         │ CopyOnWriteArrayList                                │
│ Set: reads >> writes          │ CopyOnWriteArraySet                                 │
│ Unbounded non-blocking queue  │ ConcurrentLinkedQueue                               │
│ Unbounded non-blocking deque  │ ConcurrentLinkedDeque                               │
│ Bounded blocking queue        │ ArrayBlockingQueue                                  │
│ Unbounded blocking queue      │ LinkedBlockingQueue                                 │
│ Priority blocking queue       │ PriorityBlockingQueue                               │
│ Hand-off (zero buffer)        │ SynchronousQueue                                    │
│ Delayed elements              │ DelayQueue                                          │
│ Blocking deque                │ LinkedBlockingDeque                                  │
│ Adaptive transfer             │ LinkedTransferQueue                                  │
├───────────────────────────────┼────────────────────────────────────────────────────┤
│ Thread-safe counter (low      │ AtomicInteger / AtomicLong                          │
│   contention)                 │                                                     │
│ Thread-safe counter (high     │ LongAdder / LongAccumulator                         │
│   contention)                 │                                                     │
│ Lock-free stack               │ ConcurrentLinkedDeque (use as stack)                │
│ Producer-Consumer             │ ArrayBlockingQueue or LinkedBlockingQueue            │
│ Work-stealing                 │ LinkedTransferQueue or ForkJoinPool                  │
└───────────────────────────────┴────────────────────────────────────────────────────┘
*/
```

---

public class AtomicDemo {
    
    public static void main(String[] args) throws InterruptedException {
        
        // ==================== AtomicInteger ====================
        AtomicInteger counter = new AtomicInteger(0);
        
        counter.incrementAndGet();   // ++counter (returns new value)
        counter.getAndIncrement();   // counter++ (returns old value)
        counter.decrementAndGet();   // --counter
        counter.getAndDecrement();   // counter--
        counter.addAndGet(5);        // counter += 5 (returns new)
        counter.getAndAdd(3);        // (returns old, then adds 3)
        counter.set(100);            // Direct set
        int val = counter.get();     // Direct get
        
        // compareAndSet (CAS operation)
        boolean success = counter.compareAndSet(100, 200); // If current==100, set to 200
        System.out.println("CAS success: " + success + ", value: " + counter.get()); // true, 200
        
        // Functional update (Java 8)
        counter.updateAndGet(x -> x * 2);          // counter = 400
        counter.accumulateAndGet(10, Integer::sum); // counter = 410
        
        // Thread-safe counter with AtomicInteger
        AtomicInteger threadSafeCounter = new AtomicInteger(0);
        ExecutorService pool = Executors.newFixedThreadPool(10);
        
        for (int i = 0; i < 1000; i++) {
            pool.submit(threadSafeCounter::incrementAndGet);
        }
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("Thread-safe counter: " + threadSafeCounter.get()); // Always 1000
        
        // ==================== AtomicLong ====================
        AtomicLong longCounter = new AtomicLong(0L);
        longCounter.incrementAndGet();
        // Same API as AtomicInteger but for long values
        
        // ==================== AtomicBoolean ====================
        AtomicBoolean flag = new AtomicBoolean(false);
        
        // Common pattern: ensure initialization runs once
        if (flag.compareAndSet(false, true)) {
            System.out.println("I won the race! Initializing...");
        } else {
            System.out.println("Already initialized by another thread");
        }
        
        // ==================== AtomicReference ====================
        AtomicReference<String> ref = new AtomicReference<>("initial");
        
        ref.set("updated");
        String old = ref.getAndSet("new value"); // Returns old, sets new
        
        // CAS on objects
        ref.compareAndSet("new value", "final value");
        System.out.println("Ref: " + ref.get()); // "final value"
        
        // Practical: thread-safe immutable object update
        AtomicReference<List<String>> listRef = new AtomicReference<>(List.of("A"));
        
        // Atomically add to immutable list
        listRef.updateAndGet(currentList -> {
            var newList = new java.util.ArrayList<>(currentList);
            newList.add("B");
            return List.copyOf(newList);
        });
        System.out.println("List: " + listRef.get()); // [A, B]
    }
}
```

### 5.2 Compare-And-Swap (CAS) Mechanism

```java
import java.util.concurrent.atomic.AtomicInteger;

public class CASDemo {
    
    /*
    CAS (Compare-And-Swap) is a CPU-level atomic instruction:
    
    CAS(memory_location, expected_value, new_value):
        if memory_location == expected_value:
            memory_location = new_value
            return true
        else:
            return false  (someone else changed it!)
    
    It's a single atomic hardware instruction - cannot be interrupted.
    
    Lock-free algorithms use CAS in a retry loop:
    */
    
    // Manual CAS-based increment (what AtomicInteger does internally)
    private AtomicInteger value = new AtomicInteger(0);
    
    public void casIncrement() {
        int oldValue, newValue;
        do {
            oldValue = value.get();           // Read current value
            newValue = oldValue + 1;          // Compute new value
        } while (!value.compareAndSet(oldValue, newValue)); // Retry until CAS succeeds
        // If another thread changed value between get() and CAS, CAS fails → retry
    }
    
    // CAS-based stack (lock-free data structure)
    static class LockFreeStack<T> {
        private final AtomicReference<Node<T>> top = new AtomicReference<>(null);
        
        static class Node<T> {
            final T value;
            final Node<T> next;
            Node(T value, Node<T> next) {
                this.value = value;
                this.next = next;
            }
        }
        
        public void push(T item) {
            Node<T> newNode;
            Node<T> oldTop;
            do {
                oldTop = top.get();
                newNode = new Node<>(item, oldTop);
            } while (!top.compareAndSet(oldTop, newNode)); // Retry if top changed
        }
        
        public T pop() {
            Node<T> oldTop;
            Node<T> newTop;
            do {
                oldTop = top.get();
                if (oldTop == null) return null;
                newTop = oldTop.next;
            } while (!top.compareAndSet(oldTop, newTop));
            return oldTop.value;
        }
    }
    
    /*
    CAS vs Locks:
    
    CAS (Optimistic):
    + No context switching (no blocking)
    + Better performance under low-medium contention
    + No deadlock possible
    - Busy-waiting under high contention (spinning)
    - ABA problem (see AtomicStampedReference)
    - Complex algorithms
    
    Locks (Pessimistic):
    + Simple programming model
    + Better under very high contention (no spinning)
    + Can hold complex critical sections
    - Context switching overhead
    - Deadlock possible
    - Thread parking/unparking cost
    */
    
    private static final java.util.concurrent.atomic.AtomicReference<Node> topRef = 
        new java.util.concurrent.atomic.AtomicReference<>(null);
    
    static class Node<T> {
        T val;
        Node<T> next;
    }
}
```

### 5.3 LongAdder & LongAccumulator (High Contention)

```java
import java.util.concurrent.atomic.*;
import java.util.concurrent.*;

public class LongAdderDemo {
    
    /*
    Problem: Under HIGH contention, AtomicLong's CAS loop retries excessively.
    
    Solution: LongAdder maintains MULTIPLE cells (striped counters).
    Each thread updates its own cell → reduces contention.
    sum() adds all cells together.
    
    Trade-off: Higher memory usage, but MUCH better throughput under contention.
    */
    
    public static void main(String[] args) throws Exception {
        
        // ==================== LongAdder ====================
        LongAdder adder = new LongAdder();
        
        adder.increment();     // +1
        adder.decrement();     // -1
        adder.add(10);         // +10
        
        long total = adder.sum();          // Get current total
        long totalAndReset = adder.sumThenReset(); // Get total and reset to 0
        
        // Performance comparison: AtomicLong vs LongAdder
        int numThreads = 10;
        int iterations = 1_000_000;
        
        // AtomicLong test
        AtomicLong atomicLong = new AtomicLong(0);
        long start = System.nanoTime();
        ExecutorService pool1 = Executors.newFixedThreadPool(numThreads);
        for (int i = 0; i < numThreads; i++) {
            pool1.submit(() -> {
                for (int j = 0; j < iterations; j++) atomicLong.incrementAndGet();
            });
        }
        pool1.shutdown();
        pool1.awaitTermination(30, TimeUnit.SECONDS);
        long atomicTime = System.nanoTime() - start;
        
        // LongAdder test
        LongAdder longAdder = new LongAdder();
        start = System.nanoTime();
        ExecutorService pool2 = Executors.newFixedThreadPool(numThreads);
        for (int i = 0; i < numThreads; i++) {
            pool2.submit(() -> {
                for (int j = 0; j < iterations; j++) longAdder.increment();
            });
        }
        pool2.shutdown();
        pool2.awaitTermination(30, TimeUnit.SECONDS);
        long adderTime = System.nanoTime() - start;
        
        System.out.println("AtomicLong: " + atomicLong.get() + " in " + atomicTime/1_000_000 + "ms");
        System.out.println("LongAdder:  " + longAdder.sum() + " in " + adderTime/1_000_000 + "ms");
        // LongAdder is typically 2-5x faster under high contention
        
        // ==================== LongAccumulator (generalized) ====================
        // Custom accumulation function
        LongAccumulator maxAccumulator = new LongAccumulator(Long::max, Long.MIN_VALUE);
        maxAccumulator.accumulate(5);
        maxAccumulator.accumulate(3);
        maxAccumulator.accumulate(8);
        System.out.println("Max: " + maxAccumulator.get()); // 8
        
        LongAccumulator sumAccumulator = new LongAccumulator(Long::sum, 0);
        sumAccumulator.accumulate(5);
        sumAccumulator.accumulate(3);
        sumAccumulator.accumulate(8);
        System.out.println("Sum: " + sumAccumulator.get()); // 16
        
        // DoubleAdder / DoubleAccumulator for floating-point
        DoubleAdder doubleAdder = new DoubleAdder();
        doubleAdder.add(1.5);
        doubleAdder.add(2.5);
        System.out.println("Double sum: " + doubleAdder.sum()); // 4.0
    }
}

/*
When to use what:
- AtomicLong: Low contention, need exact real-time value (get())
- LongAdder: High contention counters (metrics, statistics)
             Only need periodic sum() (not real-time exact value)
- LongAccumulator: Custom reduction operations under contention
*/
```

### 5.4 AtomicStampedReference (ABA Problem)

```java
import java.util.concurrent.atomic.AtomicStampedReference;

public class ABADemo {
    
    /*
    THE ABA PROBLEM:
    
    Thread 1: reads value A, gets suspended
    Thread 2: changes A → B → A (back to A)
    Thread 1: resumes, CAS sees A == A → succeeds!
              But the value has changed and changed back!
    
    This matters when the "A" you see is semantically different
    (e.g., same pointer but different node in a stack).
    
    Solution: AtomicStampedReference adds a version stamp.
    CAS checks both value AND stamp.
    */
    
    public static void main(String[] args) throws InterruptedException {
        
        // Without stamp: ABA problem
        // AtomicReference<String> ref = new AtomicReference<>("A");
        // Thread sees "A", another thread does A→B→A, CAS succeeds incorrectly
        
        // With stamp: ABA detected
        AtomicStampedReference<String> stampedRef = 
            new AtomicStampedReference<>("A", 0); // initial value "A", stamp 0
        
        // Thread 1: read value and stamp
        String value1 = stampedRef.getReference();
        int stamp1 = stampedRef.getStamp();
        System.out.println("T1 read: " + value1 + ", stamp: " + stamp1);
        
        // Thread 2: changes A→B→A (incrementing stamp each time)
        Thread t2 = new Thread(() -> {
            int stamp = stampedRef.getStamp();
            stampedRef.compareAndSet("A", "B", stamp, stamp + 1); // A→B, stamp 0→1
            System.out.println("T2: A→B, stamp: " + stampedRef.getStamp());
            
            stamp = stampedRef.getStamp();
            stampedRef.compareAndSet("B", "A", stamp, stamp + 1); // B→A, stamp 1→2
            System.out.println("T2: B→A, stamp: " + stampedRef.getStamp());
        });
        t2.start();
        t2.join();
        
        // Thread 1: tries CAS with old stamp
        boolean success = stampedRef.compareAndSet(
            value1,   // expected reference: "A"
            "C",      // new reference
            stamp1,   // expected stamp: 0
            stamp1 + 1 // new stamp
        );
        
        System.out.println("T1 CAS success: " + success); // FALSE! Stamp mismatch (0 != 2)
        System.out.println("Current value: " + stampedRef.getReference()); // Still "A"
        System.out.println("Current stamp: " + stampedRef.getStamp());     // 2
        
        // The ABA change was DETECTED via the stamp!
    }
}

/*
Also available:
- AtomicMarkableReference: uses boolean mark instead of int stamp
  Useful for: marking nodes as "logically deleted" in concurrent data structures
*/
```

---

## 6. Synchronization Utilities

### 6.1 CountDownLatch

```java
import java.util.concurrent.*;

public class CountDownLatchDemo {
    
    /*
    CountDownLatch: One or more threads wait until N events occur.
    
    - Initialize with count N
    - countDown() decrements count
    - await() blocks until count reaches 0
    - Cannot be reset! (use CyclicBarrier for reusable)
    
    Use cases:
    - Wait for N services to start before accepting requests
    - Wait for N workers to complete before proceeding
    - Starting gun: all threads wait, then start simultaneously
    */
    
    public static void main(String[] args) throws InterruptedException {
        
        // ==================== Example 1: Wait for services to initialize ====================
        int serviceCount = 3;
        CountDownLatch latch = new CountDownLatch(serviceCount);
        
        for (int i = 1; i <= serviceCount; i++) {
            final int serviceId = i;
            new Thread(() -> {
                try {
                    Thread.sleep((long)(Math.random() * 2000));
                    System.out.println("Service " + serviceId + " initialized");
                    latch.countDown(); // Signal: one service ready
                } catch (InterruptedException e) {}
            }).start();
        }
        
        System.out.println("Waiting for all services to initialize...");
        latch.await(); // Block until count reaches 0
        System.out.println("All services ready! Starting application.");
        
        // ==================== Example 2: Starting gun (all threads start together) ====================
        CountDownLatch startGun = new CountDownLatch(1); // Only 1 count
        int racerCount = 5;
        
        for (int i = 1; i <= racerCount; i++) {
            final int id = i;
            new Thread(() -> {
                try {
                    System.out.println("Racer " + id + " ready");
                    startGun.await(); // All threads wait here
                    System.out.println("Racer " + id + " GO! " + System.currentTimeMillis());
                } catch (InterruptedException e) {}
            }).start();
        }
        
        Thread.sleep(1000);
        System.out.println("Bang!!");
        startGun.countDown(); // All racers start simultaneously
        
        // await with timeout
        // boolean completed = latch.await(5, TimeUnit.SECONDS); // Returns false if timeout
    }
}
```

### 6.2 CyclicBarrier

```java
import java.util.concurrent.*;

public class CyclicBarrierDemo {
    
    /*
    CyclicBarrier: N threads wait for EACH OTHER at a barrier point.
    
    - All N threads must call await() before any can proceed
    - CAN be reused (cyclic!) after all threads pass
    - Optional barrier action runs when all threads arrive
    
    Difference from CountDownLatch:
    - CountDownLatch: threads count down, one thread waits
    - CyclicBarrier: ALL threads wait for each other
    - CountDownLatch: one-shot
    - CyclicBarrier: reusable
    */
    
    public static void main(String[] args) {
        int parties = 3;
        
        // Barrier action runs when all parties arrive (runs in last arriving thread)
        CyclicBarrier barrier = new CyclicBarrier(parties, () -> {
            System.out.println("=== All threads arrived! Barrier action executing ===");
        });
        
        for (int i = 1; i <= parties; i++) {
            final int id = i;
            new Thread(() -> {
                try {
                    // Phase 1
                    System.out.println("Thread " + id + " doing Phase 1 work");
                    Thread.sleep((long)(Math.random() * 2000));
                    System.out.println("Thread " + id + " waiting at barrier (Phase 1 done)");
                    barrier.await(); // Wait for all threads
                    
                    // Phase 2 (barrier is reused!)
                    System.out.println("Thread " + id + " doing Phase 2 work");
                    Thread.sleep((long)(Math.random() * 1000));
                    System.out.println("Thread " + id + " waiting at barrier (Phase 2 done)");
                    barrier.await(); // Wait again
                    
                    System.out.println("Thread " + id + " finished all phases!");
                    
                } catch (InterruptedException | BrokenBarrierException e) {
                    e.printStackTrace();
                }
            }).start();
        }
    }
}

/*
Output pattern:
Thread 1 doing Phase 1 work
Thread 2 doing Phase 1 work
Thread 3 doing Phase 1 work
Thread 2 waiting at barrier (Phase 1 done)
Thread 1 waiting at barrier (Phase 1 done)
Thread 3 waiting at barrier (Phase 1 done)
=== All threads arrived! Barrier action executing ===
Thread 3 doing Phase 2 work
Thread 1 doing Phase 2 work
Thread 2 doing Phase 2 work
...
=== All threads arrived! Barrier action executing ===
Thread 1 finished all phases!
Thread 2 finished all phases!
Thread 3 finished all phases!
*/
```

### 6.3 Semaphore

```java
import java.util.concurrent.*;

public class SemaphoreDemo {
    
    /*
    Semaphore: Controls access to N permits (resources).
    
    - acquire(): take a permit (block if none available)
    - release(): return a permit
    - Not tied to specific thread (unlike Lock)
    - Can be used for rate limiting, connection pooling
    
    Binary semaphore (permits=1) ≈ mutex/lock
    Counting semaphore (permits=N) = resource pool
    */
    
    // ==================== Example 1: Connection Pool ====================
    static class ConnectionPool {
        private final Semaphore semaphore;
        private final BlockingQueue<String> connections;
        
        public ConnectionPool(int maxConnections) {
            this.semaphore = new Semaphore(maxConnections, true); // fair=true
            this.connections = new LinkedBlockingQueue<>();
            for (int i = 0; i < maxConnections; i++) {
                connections.add("Connection-" + i);
            }
        }
        
        public String acquire() throws InterruptedException {
            semaphore.acquire(); // Block if no permits available
            return connections.poll();
        }
        
        public void release(String connection) {
            connections.offer(connection);
            semaphore.release(); // Return permit
        }
        
        public int availableConnections() {
            return semaphore.availablePermits();
        }
    }
    
    // ==================== Example 2: Rate Limiter ====================
    static class RateLimiter {
        private final Semaphore semaphore;
        
        public RateLimiter(int maxConcurrent) {
            this.semaphore = new Semaphore(maxConcurrent);
        }
        
        public void executeWithLimit(Runnable task) {
            try {
                semaphore.acquire();
                try {
                    task.run();
                } finally {
                    semaphore.release();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        
        // Non-blocking version
        public boolean tryExecute(Runnable task) {
            if (semaphore.tryAcquire()) {
                try {
                    task.run();
                    return true;
                } finally {
                    semaphore.release();
                }
            }
            return false; // Too many concurrent executions
        }
    }
    
    public static void main(String[] args) throws InterruptedException {
        // Connection pool with max 3 connections
        ConnectionPool pool = new ConnectionPool(3);
        
        for (int i = 0; i < 10; i++) {
            final int id = i;
            new Thread(() -> {
                try {
                    System.out.println("Thread " + id + " requesting connection. Available: " 
                                     + pool.availableConnections());
                    String conn = pool.acquire();
                    System.out.println("Thread " + id + " got " + conn);
                    Thread.sleep(2000); // Use connection
                    pool.release(conn);
                    System.out.println("Thread " + id + " released " + conn);
                } catch (InterruptedException e) {}
            }).start();
        }
        
        // Rate limiter: max 2 concurrent operations
        RateLimiter limiter = new RateLimiter(2);
        ExecutorService executor = Executors.newFixedThreadPool(10);
        
        for (int i = 0; i < 10; i++) {
            final int id = i;
            executor.submit(() -> limiter.executeWithLimit(() -> {
                System.out.println("Task " + id + " executing");
                try { Thread.sleep(1000); } catch (InterruptedException e) {}
            }));
        }
        
        executor.shutdown();
    }
}
```

### 6.4 Phaser

```java
import java.util.concurrent.Phaser;

public class PhaserDemo {
    
    /*
    Phaser: Flexible, reusable barrier (generalization of CountDownLatch + CyclicBarrier).
    
    Features:
    - Dynamic registration/deregistration of parties
    - Multiple phases (like CyclicBarrier but more flexible)
    - Supports tiering (tree of Phasers for large numbers of threads)
    - Can terminate early
    
    Methods:
    - register(): add a party
    - arrive(): arrive but don't wait
    - arriveAndAwaitAdvance(): arrive and wait (like CyclicBarrier.await())
    - arriveAndDeregister(): arrive and remove self from future phases
    - getPhase(): current phase number
    */
    
    public static void main(String[] args) throws InterruptedException {
        
        // ==================== Basic usage ====================
        Phaser phaser = new Phaser(1); // Register self (main thread)
        
        for (int i = 1; i <= 3; i++) {
            final int id = i;
            phaser.register(); // Dynamically add party
            
            new Thread(() -> {
                for (int phase = 0; phase < 3; phase++) {
                    System.out.println("Thread " + id + " working on phase " + phase);
                    try { Thread.sleep((long)(Math.random() * 1000)); } catch (InterruptedException e) {}
                    
                    if (id == 2 && phase == 1) {
                        // Thread 2 leaves after phase 1
                        System.out.println("Thread " + id + " deregistering after phase " + phase);
                        phaser.arriveAndDeregister();
                        return;
                    }
                    
                    phaser.arriveAndAwaitAdvance(); // Wait for all parties
                    System.out.println("Thread " + id + " completed phase " + phase);
                }
                phaser.arriveAndDeregister();
            }).start();
        }
        
        // Main thread controls phases
        for (int phase = 0; phase < 3; phase++) {
            phaser.arriveAndAwaitAdvance(); // Main participates too
            System.out.println("=== Phase " + phase + " completed ===");
        }
        
        phaser.arriveAndDeregister(); // Main deregisters
    }
}
```

### 6.5 Exchanger

```java
import java.util.concurrent.Exchanger;

public class ExchangerDemo {
    
    /*
    Exchanger: Two threads exchange objects at a rendezvous point.
    
    - First thread to call exchange() blocks until the second arrives
    - When both arrive, they swap their objects and proceed
    - Use case: producer/consumer pipeline, genetic algorithms
    */
    
    public static void main(String[] args) {
        Exchanger<String> exchanger = new Exchanger<>();
        
        // Thread 1: fills buffer, exchanges with empty buffer from Thread 2
        Thread producer = new Thread(() -> {
            try {
                for (int i = 0; i < 3; i++) {
                    String produced = "Data-" + i;
                    System.out.println("Producer offering: " + produced);
                    
                    String received = exchanger.exchange(produced); // Blocks until consumer arrives
                    System.out.println("Producer received empty buffer: " + received);
                }
            } catch (InterruptedException e) {}
        });
        
        // Thread 2: provides empty buffer, gets filled buffer
        Thread consumer = new Thread(() -> {
            try {
                for (int i = 0; i < 3; i++) {
                    String emptyBuffer = "EmptyBuffer-" + i;
                    
                    String received = exchanger.exchange(emptyBuffer); // Blocks until producer arrives
                    System.out.println("Consumer received: " + received);
                    System.out.println("Consumer processing: " + received);
                    Thread.sleep(500);
                }
            } catch (InterruptedException e) {}
        });
        
        producer.start();
        consumer.start();
    }
}

/*
Output:
Producer offering: Data-0
Consumer received: Data-0
Producer received empty buffer: EmptyBuffer-0
Consumer processing: Data-0
Producer offering: Data-1
Consumer received: Data-1
Producer received empty buffer: EmptyBuffer-1
...
*/
```

---

## 7. Fork/Join Framework

### 7.1 RecursiveTask & RecursiveAction

```java
import java.util.concurrent.*;
import java.util.Arrays;

public class ForkJoinDemo {
    
    /*
    Fork/Join Framework: Divide-and-conquer parallelism.
    
    - ForkJoinPool: Special executor optimized for fork/join tasks
    - RecursiveTask<V>: Returns a value
    - RecursiveAction: No return value (void)
    
    Pattern:
    if (problem is small enough)
        solve directly (sequential)
    else
        fork() - split into subtasks, submit to pool
        join() - wait for subtask results
        combine results
    
    Work-Stealing: Idle threads steal tasks from busy threads' deques.
    Each thread has a double-ended queue (deque):
    - push/pop own tasks from the TAIL (LIFO)
    - steal from other threads' HEAD (FIFO)
    This keeps tasks local (cache-friendly) and balances load.
    */
    
    // ==================== RecursiveTask: Parallel Sum ====================
    static class ParallelSum extends RecursiveTask<Long> {
        private final int[] array;
        private final int start, end;
        private static final int THRESHOLD = 1000; // Below this, compute sequentially
        
        public ParallelSum(int[] array, int start, int end) {
            this.array = array;
            this.start = start;
            this.end = end;
        }
        
        @Override
        protected Long compute() {
            int length = end - start;
            
            // Base case: small enough to compute directly
            if (length <= THRESHOLD) {
                long sum = 0;
                for (int i = start; i < end; i++) {
                    sum += array[i];
                }
                return sum;
            }
            
            // Recursive case: split and fork
            int mid = start + length / 2;
            
            ParallelSum leftTask = new ParallelSum(array, start, mid);
            ParallelSum rightTask = new ParallelSum(array, mid, end);
            
            leftTask.fork();  // Submit left subtask to pool (async)
            Long rightResult = rightTask.compute(); // Compute right in current thread
            Long leftResult = leftTask.join();  // Wait for left result
            
            return leftResult + rightResult;
        }
    }
    
    // ==================== RecursiveAction: Parallel Array Increment ====================
    static class ParallelIncrement extends RecursiveAction {
        private final int[] array;
        private final int start, end;
        private static final int THRESHOLD = 1000;
        
        public ParallelIncrement(int[] array, int start, int end) {
            this.array = array;
            this.start = start;
            this.end = end;
        }
        
        @Override
        protected void compute() {
            if (end - start <= THRESHOLD) {
                // Base case
                for (int i = start; i < end; i++) {
                    array[i]++;
                }
            } else {
                // Split
                int mid = start + (end - start) / 2;
                ParallelIncrement left = new ParallelIncrement(array, start, mid);
                ParallelIncrement right = new ParallelIncrement(array, mid, end);
                
                invokeAll(left, right); // Fork both and join both
            }
        }
    }
    
    public static void main(String[] args) {
        int[] array = new int[10_000_000];
        Arrays.fill(array, 1);
        
        ForkJoinPool pool = new ForkJoinPool(); // Default: available processors
        // Or: ForkJoinPool.commonPool() - shared pool used by parallel streams
        
        // Parallel sum
        long start = System.nanoTime();
        long sum = pool.invoke(new ParallelSum(array, 0, array.length));
        long elapsed = System.nanoTime() - start;
        
        System.out.println("Sum: " + sum + " in " + elapsed/1_000_000 + "ms");
        System.out.println("Pool parallelism: " + pool.getParallelism());
        System.out.println("Pool size: " + pool.getPoolSize());
        System.out.println("Steal count: " + pool.getStealCount());
        
        pool.shutdown();
    }
}
```

### 7.2 Parallel Merge Sort

```java
import java.util.concurrent.*;
import java.util.Arrays;

public class ParallelMergeSort extends RecursiveAction {
    private final int[] array;
    private final int[] temp;
    private final int start, end;
    private static final int THRESHOLD = 1024;
    
    public ParallelMergeSort(int[] array, int[] temp, int start, int end) {
        this.array = array;
        this.temp = temp;
        this.start = start;
        this.end = end;
    }
    
    @Override
    protected void compute() {
        if (end - start <= THRESHOLD) {
            // Small enough: use Arrays.sort (Tim Sort)
            Arrays.sort(array, start, end);
            return;
        }
        
        int mid = start + (end - start) / 2;
        
        // Sort two halves in parallel
        ParallelMergeSort left = new ParallelMergeSort(array, temp, start, mid);
        ParallelMergeSort right = new ParallelMergeSort(array, temp, mid, end);
        
        invokeAll(left, right); // Fork both subtasks
        
        // Merge sorted halves
        merge(start, mid, end);
    }
    
    private void merge(int start, int mid, int end) {
        // Copy to temp
        System.arraycopy(array, start, temp, start, end - start);
        
        int i = start, j = mid, k = start;
        
        while (i < mid && j < end) {
            if (temp[i] <= temp[j]) {
                array[k++] = temp[i++];
            } else {
                array[k++] = temp[j++];
            }
        }
        
        while (i < mid) array[k++] = temp[i++];
        // No need to copy remaining right side (already in place)
    }
    
    public static void main(String[] args) {
        int size = 10_000_000;
        int[] array = new int[size];
        java.util.Random rand = new java.util.Random();
        for (int i = 0; i < size; i++) array[i] = rand.nextInt(1_000_000);
        
        int[] temp = new int[size];
        
        ForkJoinPool pool = ForkJoinPool.commonPool();
        
        long start = System.nanoTime();
        pool.invoke(new ParallelMergeSort(array, temp, 0, size));
        long elapsed = System.nanoTime() - start;
        
        System.out.println("Sorted " + size + " elements in " + elapsed/1_000_000 + "ms");
        System.out.println("First 10: " + Arrays.toString(Arrays.copyOf(array, 10)));
        System.out.println("Is sorted: " + isSorted(array));
    }
    
    private static boolean isSorted(int[] arr) {
        for (int i = 1; i < arr.length; i++) {
            if (arr[i] < arr[i-1]) return false;
        }
        return true;
    }
}
```

---

## 8. Virtual Threads (Java 21)

### 8.1 Thread.ofVirtual()

```java
import java.util.concurrent.*;
import java.util.*;
import java.time.*;

public class VirtualThreadsDemo {
    
    /*
    VIRTUAL THREADS (Project Loom, Java 21):
    
    Platform threads (traditional):
    - 1:1 mapping with OS thread
    - ~1MB stack each
    - Creating thousands is expensive
    - Context switching is OS-level
    
    Virtual threads:
    - M:N mapping (many virtual threads on few OS threads)
    - ~few KB stack (grows on demand)
    - Can create MILLIONS cheaply
    - Mounted/unmounted from carrier threads
    - When a virtual thread blocks (I/O), it's unmounted → carrier thread handles another virtual thread
    
    KEY INSIGHT: Virtual threads make blocking code as efficient as async code,
    but MUCH simpler to write, debug, and understand.
    */
    
    public static void main(String[] args) throws Exception {
        
        // ==================== Creating virtual threads ====================
        
        // Method 1: Thread.ofVirtual()
        Thread vThread1 = Thread.ofVirtual()
            .name("virtual-1")
            .start(() -> {
                System.out.println("Virtual thread: " + Thread.currentThread());
                System.out.println("Is virtual: " + Thread.currentThread().isVirtual());
            });
        vThread1.join();
        
        // Method 2: Thread.startVirtualThread (convenience)
        Thread vThread2 = Thread.startVirtualThread(() -> {
            System.out.println("Quick virtual thread");
        });
        vThread2.join();
        
        // Method 3: Virtual thread executor (PREFERRED for production)
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            // Each task gets its own virtual thread
            // Can handle millions of concurrent tasks!
            
            List<Future<String>> futures = new ArrayList<>();
            
            for (int i = 0; i < 100_000; i++) {
                final int id = i;
                futures.add(executor.submit(() -> {
                    Thread.sleep(1000); // Simulate I/O - virtual thread unmounts!
                    return "Result-" + id;
                }));
            }
            
            // 100,000 concurrent tasks, each sleeping 1 second
            // With platform threads: would need 100K OS threads (impossible)
            // With virtual threads: uses ~few OS threads efficiently
            
            System.out.println("First result: " + futures.get(0).get());
            System.out.println("Last result: " + futures.get(99_999).get());
        }
        
        // ==================== Virtual thread factory ====================
        ThreadFactory factory = Thread.ofVirtual()
            .name("worker-", 0) // worker-0, worker-1, worker-2, ...
            .factory();
        
        try (ExecutorService exec = Executors.newThreadPerTaskExecutor(factory)) {
            exec.submit(() -> {
                System.out.println("Thread name: " + Thread.currentThread().getName());
            });
        }
        
        // ==================== Performance comparison ====================
        int taskCount = 10_000;
        
        // Platform threads
        long start = System.nanoTime();
        try (ExecutorService platformPool = Executors.newFixedThreadPool(200)) {
            List<Future<?>> platformFutures = new ArrayList<>();
            for (int i = 0; i < taskCount; i++) {
                platformFutures.add(platformPool.submit(() -> {
                    try { Thread.sleep(100); } catch (InterruptedException e) {}
                }));
            }
            for (Future<?> f : platformFutures) f.get();
        }
        System.out.println("Platform threads: " + (System.nanoTime() - start)/1_000_000 + "ms");
        
        // Virtual threads
        start = System.nanoTime();
        try (ExecutorService virtualPool = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<?>> virtualFutures = new ArrayList<>();
            for (int i = 0; i < taskCount; i++) {
                virtualFutures.add(virtualPool.submit(() -> {
                    try { Thread.sleep(100); } catch (InterruptedException e) {}
                }));
            }
            for (Future<?> f : virtualFutures) f.get();
        }
        System.out.println("Virtual threads: " + (System.nanoTime() - start)/1_000_000 + "ms");
        // Virtual threads will be MUCH faster for I/O-bound tasks
    }
}

/*
WHEN TO USE VIRTUAL THREADS:
✅ I/O-bound tasks (HTTP calls, DB queries, file I/O)
✅ High-concurrency servers (handling thousands of requests)
✅ Tasks that spend most time waiting/blocked
✅ Replacing async/reactive code with simpler blocking code

WHEN NOT TO USE:
❌ CPU-bound tasks (virtual threads don't add parallelism!)
❌ Tasks holding synchronized locks for long (pins carrier thread)
    → Use ReentrantLock instead of synchronized for long critical sections
❌ Tasks using ThreadLocal heavily (millions of copies)
    → Use scoped values instead

IMPORTANT CAVEATS:
- synchronized blocks PIN the virtual thread to its carrier
- Use ReentrantLock instead of synchronized for potentially blocking code
- Avoid ThreadLocal (use ScopedValue in Java 21+)
- Don't pool virtual threads (they're cheap to create)
*/
```

### 8.2 Structured Concurrency (Preview, Java 21+)

```java
import java.util.concurrent.*;
// import jdk.incubator.concurrent.StructuredTaskScope; // Preview API

public class StructuredConcurrencyDemo {
    
    /*
    STRUCTURED CONCURRENCY:
    
    Problem with unstructured concurrency:
    - Threads outlive their parent's scope
    - Hard to cancel related tasks
    - Hard to handle errors across concurrent tasks
    - Thread lifecycle not tied to code structure
    
    Solution: StructuredTaskScope ties thread lifecycle to code blocks.
    
    Like structured programming (if/else/for) replaced goto,
    structured concurrency replaces fire-and-forget threads.
    */
    
    // Record for response
    record UserProfile(String name, int age) {}
    record OrderHistory(int orderCount) {}
    record UserDashboard(UserProfile profile, OrderHistory orders) {}
    
    // Simulated services
    static UserProfile fetchProfile(int userId) throws InterruptedException {
        Thread.sleep(1000);
        if (userId < 0) throw new IllegalArgumentException("Invalid user");
        return new UserProfile("User-" + userId, 25);
    }
    
    static OrderHistory fetchOrders(int userId) throws InterruptedException {
        Thread.sleep(800);
        return new OrderHistory(userId * 3);
    }
    
    /*
    // STRUCTURED CONCURRENCY (Preview API - syntax may change)
    
    static UserDashboard fetchDashboard(int userId) throws Exception {
        // ShutdownOnFailure: If ANY subtask fails, cancel all others
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            
            // Fork concurrent subtasks (bound to this scope)
            Subtask<UserProfile> profileTask = scope.fork(() -> fetchProfile(userId));
            Subtask<OrderHistory> ordersTask = scope.fork(() -> fetchOrders(userId));
            
            // Wait for all subtasks (or first failure)
            scope.join();           // Blocks until all complete or one fails
            scope.throwIfFailed();  // Propagate exception if any failed
            
            // Both succeeded - combine results
            return new UserDashboard(profileTask.get(), ordersTask.get());
        }
        // When scope closes: all subtasks are guaranteed finished
        // No thread leaks! Lifetime is bounded by the try block.
    }
    
    // ShutdownOnSuccess: Return first successful result, cancel rest
    static String fetchFromMirrors(String resource) throws Exception {
        try (var scope = new StructuredTaskScope.ShutdownOnSuccess<String>()) {
            scope.fork(() -> fetchFromMirror1(resource));
            scope.fork(() -> fetchFromMirror2(resource));
            scope.fork(() -> fetchFromMirror3(resource));
            
            scope.join();
            return scope.result(); // Returns first successful result
            // Other tasks are cancelled automatically
        }
    }
    */
    
    // Current alternative without structured concurrency (Java 17+)
    static UserDashboard fetchDashboardClassic(int userId) throws Exception {
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Future<UserProfile> profileFuture = executor.submit(() -> fetchProfile(userId));
            Future<OrderHistory> ordersFuture = executor.submit(() -> fetchOrders(userId));
            
            UserProfile profile = profileFuture.get(5, TimeUnit.SECONDS);
            OrderHistory orders = ordersFuture.get(5, TimeUnit.SECONDS);
            
            return new UserDashboard(profile, orders);
        }
    }
    
    public static void main(String[] args) throws Exception {
        UserDashboard dashboard = fetchDashboardClassic(1);
        System.out.println("Dashboard: " + dashboard);
        // Dashboard: UserDashboard[profile=UserProfile[name=User-1, age=25], 
        //                           orders=OrderHistory[orderCount=3]]
    }
}

/*
STRUCTURED CONCURRENCY BENEFITS:
1. Thread lifetime == code block scope (no leaks)
2. Cancellation propagates to all subtasks automatically
3. Error handling is centralized (ShutdownOnFailure)
4. Observability: thread dump shows logical hierarchy
5. Composable: scopes can nest

COMPARISON:
┌────────────────────────┬──────────────────────────────────────┐
│ Approach               │ Best For                             │
├────────────────────────┼──────────────────────────────────────┤
│ Platform threads       │ CPU-bound, need OS features          │
│ Virtual threads        │ I/O-bound, high concurrency          │
│ CompletableFuture      │ Complex async pipelines              │
│ Structured Concurrency │ Scoped concurrent tasks with cleanup │
│ Reactive (WebFlux)     │ Streaming, backpressure              │
└────────────────────────┴──────────────────────────────────────┘
*/
```

---

## Quick Reference: Choosing the Right Tool

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CONCURRENCY TOOL SELECTION GUIDE                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  "I need to..."                         → Use                                   │
│  ─────────────────────────────────────────────────────────────────────────      │
│  Increment a counter atomically         → AtomicInteger / LongAdder             │
│  Protect a critical section             → synchronized / ReentrantLock          │
│  Run task in background                 → ExecutorService.submit()              │
│  Wait for a result                      → Future / CompletableFuture            │
│  Chain async operations                 → CompletableFuture                     │
│  Share data between threads safely      → ConcurrentHashMap / Atomic*           │
│  Producer-consumer pattern              → BlockingQueue                         │
│  Wait for N events                      → CountDownLatch                        │
│  N threads wait for each other          → CyclicBarrier                         │
│  Limit concurrent access                → Semaphore                             │
│  Read-heavy, write-light                → ReadWriteLock / StampedLock           │
│  Divide-and-conquer parallelism         → ForkJoinPool / RecursiveTask          │
│  Handle millions of I/O tasks           → Virtual Threads                       │
│  Scoped concurrent subtasks             → Structured Concurrency                │
│  Thread-safe lazy init (singleton)      → Double-checked locking / enum         │
│  Pass data per-thread                   → ThreadLocal                           │
│  High-contention counter                → LongAdder                             │
│  Exchange data between two threads      → Exchanger                             │
│  Flexible multi-phase barrier           → Phaser                                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```
