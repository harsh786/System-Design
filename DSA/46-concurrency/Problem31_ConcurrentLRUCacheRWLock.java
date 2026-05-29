import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem31_ConcurrentLRUCacheRWLock {
    /**
     * Problem: Concurrent LRU Cache with ReentrantReadWriteLock
     * High-throughput LRU allowing concurrent reads.
     * Time: O(1) | Space: O(capacity)
     * Production Analogy: CDN edge cache with many readers, occasional eviction writes.
     */
    private final int capacity;
    private final LinkedHashMap<String, String> map;
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

    public Problem31_ConcurrentLRUCacheRWLock(int capacity) {
        this.capacity = capacity;
        this.map = new LinkedHashMap<>(capacity, 0.75f, true);
    }

    public String get(String key) {
        rwLock.writeLock().lock(); // access-order requires write lock
        try { return map.getOrDefault(key, null); }
        finally { rwLock.writeLock().unlock(); }
    }

    public void put(String key, String value) {
        rwLock.writeLock().lock();
        try { map.put(key, value); if (map.size() > capacity) { Iterator<String> it = map.keySet().iterator(); it.next(); it.remove(); } }
        finally { rwLock.writeLock().unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem31_ConcurrentLRUCacheRWLock cache = new Problem31_ConcurrentLRUCacheRWLock(3);
        cache.put("a", "1"); cache.put("b", "2"); cache.put("c", "3");
        cache.put("d", "4"); // evicts "a"
        System.out.println("a: " + cache.get("a")); // null
        System.out.println("b: " + cache.get("b")); // 2
    }
}
