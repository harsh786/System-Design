/**
 * Problem: Semaphore-based Connection Pool
 * Limit concurrent DB connections using semaphore.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: HikariCP connection pool limiting concurrent DB connections.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem16_SemaphoreConnectionPool {
    private final Semaphore semaphore;
    private final Queue<String> pool = new LinkedList<>();

    public Problem16_SemaphoreConnectionPool(int size) {
        semaphore = new Semaphore(size);
        for (int i = 0; i < size; i++) pool.add("Connection-" + i);
    }

    public String acquire() throws InterruptedException {
        semaphore.acquire();
        synchronized (pool) { return pool.poll(); }
    }

    public void release(String conn) {
        synchronized (pool) { pool.add(conn); }
        semaphore.release();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem16_SemaphoreConnectionPool cp = new Problem16_SemaphoreConnectionPool(2);
        Runnable task = () -> {
            try {
                String c = cp.acquire(); System.out.println(Thread.currentThread().getName() + " got " + c);
                Thread.sleep(100); cp.release(c);
            } catch (InterruptedException e) {}
        };
        for (int i = 0; i < 5; i++) new Thread(task, "T" + i).start();
        Thread.sleep(1000);
    }
}
