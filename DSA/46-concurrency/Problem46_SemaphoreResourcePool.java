import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem46_SemaphoreResourcePool {
    /**
     * Problem: Semaphore Resource Pool
     * Generic resource pool using Semaphore.
     * Time: O(1) acquire/release | Space: O(pool_size)
     * Production Analogy: Thread pool, DB connection pool, socket pool.
     */
    private final Semaphore sem;
    private final BlockingQueue<Object> resources;

    public Problem46_SemaphoreResourcePool(int size) {
        sem = new Semaphore(size);
        resources = new LinkedBlockingQueue<>();
        for (int i = 0; i < size; i++) resources.add("Resource-" + i);
    }

    public Object acquire() throws InterruptedException {
        sem.acquire();
        return resources.take();
    }

    public void release(Object resource) {
        resources.add(resource);
        sem.release();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem46_SemaphoreResourcePool pool = new Problem46_SemaphoreResourcePool(2);
        for (int i = 0; i < 5; i++) {
            final int id = i;
            new Thread(() -> {
                try { Object r = pool.acquire(); System.out.println("T" + id + " got " + r); Thread.sleep(100); pool.release(r); }
                catch (InterruptedException e) {}
            }).start();
        }
        Thread.sleep(1000);
    }
}
