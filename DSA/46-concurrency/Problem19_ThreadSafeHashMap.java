/**
 * Problem: Thread-safe HashMap (Striped Locking)
 * HashMap with segment-level locking for better concurrency.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: ConcurrentHashMap internals - segment locks for high throughput.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem19_ThreadSafeHashMap {
    private static final int NUM_STRIPES = 16;
    private final ReentrantLock[] locks = new ReentrantLock[NUM_STRIPES];
    private final Map<Integer, Integer>[] buckets;

    @SuppressWarnings("unchecked")
    public Problem19_ThreadSafeHashMap() {
        buckets = new HashMap[NUM_STRIPES];
        for (int i = 0; i < NUM_STRIPES; i++) { locks[i] = new ReentrantLock(); buckets[i] = new HashMap<>(); }
    }

    private int stripe(int key) { return Math.abs(key % NUM_STRIPES); }

    public void put(int key, int value) {
        int s = stripe(key); locks[s].lock();
        try { buckets[s].put(key, value); } finally { locks[s].unlock(); }
    }

    public Integer get(int key) {
        int s = stripe(key); locks[s].lock();
        try { return buckets[s].get(key); } finally { locks[s].unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem19_ThreadSafeHashMap map = new Problem19_ThreadSafeHashMap();
        Thread t1 = new Thread(() -> { for (int i = 0; i < 100; i++) map.put(i, i * 10); });
        Thread t2 = new Thread(() -> { for (int i = 0; i < 100; i++) map.put(i + 100, i * 20); });
        t1.start(); t2.start(); t1.join(); t2.join();
        System.out.println("Get 50: " + map.get(50));
        System.out.println("Get 150: " + map.get(150));
    }
}
