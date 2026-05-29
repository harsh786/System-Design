import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem27_ThreadPoolFromScratch {
    /**
     * Problem: Thread Pool from Scratch
     * Fixed-size thread pool that accepts and executes tasks.
     * Approach: Worker threads pulling from shared blocking queue.
     * Time: O(1) submit
     * Production Analogy: Tomcat thread pool handling HTTP requests.
     */
    private final BlockingQueue<Runnable> taskQueue;
    private final List<Thread> workers = new ArrayList<>();
    private volatile boolean shutdown = false;

    public Problem27_ThreadPoolFromScratch(int numThreads, int queueSize) {
        taskQueue = new LinkedBlockingQueue<>(queueSize);
        for (int i = 0; i < numThreads; i++) {
            Thread t = new Thread(() -> {
                while (!shutdown || !taskQueue.isEmpty()) {
                    try { Runnable task = taskQueue.poll(100, TimeUnit.MILLISECONDS); if (task != null) task.run(); }
                    catch (InterruptedException e) { break; }
                }
            }, "Worker-" + i);
            t.start();
            workers.add(t);
        }
    }

    public void submit(Runnable task) throws InterruptedException { taskQueue.put(task); }

    public void shutdown() throws InterruptedException {
        shutdown = true;
        for (Thread t : workers) t.join();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem27_ThreadPoolFromScratch pool = new Problem27_ThreadPoolFromScratch(3, 10);
        for (int i = 0; i < 8; i++) {
            final int id = i;
            pool.submit(() -> System.out.println(Thread.currentThread().getName() + " executing task " + id));
        }
        Thread.sleep(500);
        pool.shutdown();
        System.out.println("Pool shut down");
    }
}
