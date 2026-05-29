import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem47_StampedLockCache {
    /**
     * Problem: StampedLock Cache
     * Cache using StampedLock for optimistic reads.
     * Time: O(1) | Space: O(n)
     * Production Analogy: High-read-throughput config cache with rare updates.
     */
    private final Map<String, String> cache = new HashMap<>();
    private final StampedLock sl = new StampedLock();

    public String get(String key) {
        long stamp = sl.tryOptimisticRead();
        String val = cache.get(key);
        if (!sl.validate(stamp)) {
            stamp = sl.readLock();
            try { val = cache.get(key); } finally { sl.unlockRead(stamp); }
        }
        return val;
    }

    public void put(String key, String value) {
        long stamp = sl.writeLock();
        try { cache.put(key, value); } finally { sl.unlockWrite(stamp); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem47_StampedLockCache c = new Problem47_StampedLockCache();
        c.put("key1", "value1");
        Thread[] ts = new Thread[10];
        for (int i = 0; i < 10; i++) { ts[i] = new Thread(() -> System.out.println(c.get("key1"))); ts[i].start(); }
        for (Thread t : ts) t.join();
    }
}
