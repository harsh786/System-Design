import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem26_AsyncTaskScheduler {
    /**
     * Problem: Async Task Scheduler
     * Schedule tasks with delays, execute them asynchronously.
     * Approach: PriorityQueue sorted by execution time + worker thread.
     * Time: O(log n) schedule, O(1) execute
     * Production Analogy: Cron job scheduler, delayed message delivery in SQS.
     */
    private final PriorityQueue<long[]> taskQueue = new PriorityQueue<>((a, b) -> Long.compare(a[0], b[0]));
    private final Map<Long, Runnable> tasks = new HashMap<>();
    private long taskId = 0;
    private final Object lock = new Object();

    public void schedule(Runnable task, long delayMs) {
        synchronized (lock) {
            long executeAt = System.currentTimeMillis() + delayMs;
            taskQueue.add(new long[]{executeAt, taskId});
            tasks.put(taskId++, task);
            lock.notifyAll();
        }
    }

    public void start() {
        new Thread(() -> {
            while (true) {
                synchronized (lock) {
                    try {
                        while (taskQueue.isEmpty()) lock.wait();
                        long delay = taskQueue.peek()[0] - System.currentTimeMillis();
                        if (delay > 0) { lock.wait(delay); continue; }
                        long[] entry = taskQueue.poll();
                        Runnable task = tasks.remove(entry[1]);
                        if (task != null) task.run();
                    } catch (InterruptedException e) { break; }
                }
            }
        }, "scheduler").start();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem26_AsyncTaskScheduler scheduler = new Problem26_AsyncTaskScheduler();
        scheduler.start();
        scheduler.schedule(() -> System.out.println("Task 1 (200ms delay)"), 200);
        scheduler.schedule(() -> System.out.println("Task 2 (100ms delay)"), 100);
        scheduler.schedule(() -> System.out.println("Task 3 (50ms delay)"), 50);
        Thread.sleep(500);
        System.exit(0);
    }
}
