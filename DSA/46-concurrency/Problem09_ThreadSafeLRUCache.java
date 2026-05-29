/**
 * Problem: Thread-safe LRU Cache
 * LRU cache with get/put that is safe for concurrent access.
 * 
 * Approach: LinkedHashMap + ReentrantReadWriteLock for concurrent reads, exclusive writes.
 * Time Complexity: O(1) get/put
 * Space Complexity: O(capacity)
 * 
 * Production Analogy: Redis-like in-memory cache serving concurrent API requests.
 */
import java.util.*;
import java.util.concurrent.locks.*;

public class Problem09_ThreadSafeLRUCache {
    private final int capacity;
    private final LinkedHashMap<Integer, Integer> map;
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

    public Problem09_ThreadSafeLRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new LinkedHashMap<>(capacity, 0.75f, true) {
            protected boolean removeEldestEntry(Map.Entry<Integer, Integer> eldest) {
                return size() > Problem09_ThreadSafeLRUCache.this.capacity;
            }
        };
    }

    public int get(int key) {
        rwLock.readLock().lock();
        try { return map.getOrDefault(key, -1); }
        finally { rwLock.readLock().unlock(); }
    }

    public void put(int key, int value) {
        rwLock.writeLock().lock();
        try { map.put(key, value); }
        finally { rwLock.writeLock().unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem09_ThreadSafeLRUCache cache = new Problem09_ThreadSafeLRUCache(2);
        Thread t1 = new Thread(() -> { cache.put(1, 10); cache.put(2, 20); });
        Thread t2 = new Thread(() -> { cache.put(3, 30); System.out.println("Get 1: " + cache.get(1)); });
        t1.start(); t1.join(); t2.start(); t2.join();
        System.out.println("Get 2: " + cache.get(2));
        System.out.println("Get 3: " + cache.get(3));
    }
}
