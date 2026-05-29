import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem37_ReadWriteLockCache {
    /**
     * Problem: ReadWriteLock Cache
     * Cache allowing concurrent reads, exclusive writes.
     * Time: O(1) | Space: O(n)
     * Production Analogy: Configuration cache read by many services, updated by config service.
     */
    private final Map<String, String> cache = new HashMap<>();
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

    public String get(String key) {
        rwLock.readLock().lock();
        try { return cache.get(key); } finally { rwLock.readLock().unlock(); }
    }

    public void put(String key, String value) {
        rwLock.writeLock().lock();
        try { cache.put(key, value); } finally { rwLock.writeLock().unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem37_ReadWriteLockCache c = new Problem37_ReadWriteLockCache();
        c.put("host", "localhost");
        Thread[] readers = new Thread[5];
        for (int i = 0; i < 5; i++) { readers[i] = new Thread(() -> System.out.println(Thread.currentThread().getName() + ": " + c.get("host"))); readers[i].start(); }
        for (Thread t : readers) t.join();
    }
}
