import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem40_ScheduledExecutorDesign {
    /**
     * Problem: Scheduled Executor Design
     * Execute tasks at fixed rate or with fixed delay.
     * Approach: Min-heap of scheduled tasks + worker thread.
     * Time: O(log n) schedule | Space: O(n)
     * Production Analogy: ScheduledThreadPoolExecutor, Kubernetes CronJob controller.
     */
    private final PriorityBlockingQueue<long[]> tasks = new PriorityBlockingQueue<>(10, (a, b) -> Long.compare(a[0], b[0]));
    private final Map<Long, Runnable> runnables = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(0);

    public void scheduleAtFixedRate(Runnable task, long initialDelay, long period) {
        long id = idGen.getAndIncrement();
        runnables.put(id, task);
        tasks.add(new long[]{System.currentTimeMillis() + initialDelay, id, period});
    }

    public void start() {
        new Thread(() -> {
            while (true) {
                try {
                    long[] entry = tasks.take();
                    long delay = entry[0] - System.currentTimeMillis();
                    if (delay > 0) { Thread.sleep(delay); }
                    Runnable r = runnables.get(entry[1]);
                    if (r != null) { r.run(); tasks.add(new long[]{System.currentTimeMillis() + entry[2], entry[1], entry[2]}); }
                } catch (InterruptedException e) { break; }
            }
        }).start();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem40_ScheduledExecutorDesign exec = new Problem40_ScheduledExecutorDesign();
        exec.start();
        exec.scheduleAtFixedRate(() -> System.out.println("Tick: " + System.currentTimeMillis()), 0, 200);
        Thread.sleep(1000);
        System.exit(0);
    }
}
