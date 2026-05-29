import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.*;

/**
 * Problem 69: Lock Striping for High-Throughput HashMap
 * 
 * REAL-WORLD USAGE:
 * - Java's ConcurrentHashMap (uses lock striping / segmented locking)
 * - Memcached's internal hash table (slab-level locking)
 * - Database buffer pools (page-level latching)
 * - Connection pool management
 * 
 * KEY CONCEPTS:
 * - Instead of ONE lock for entire map → N locks, each protecting a STRIPE
 * - Key's hash determines which stripe (lock) to acquire
 * - Unrelated keys in different stripes can be accessed concurrently
 * - Concurrency level = number of stripes (typically 16-64)
 * 
 * WHY NOT JUST synchronized HashMap?
 * - Single lock = serial access = bottleneck under contention
 * - Lock striping: N threads can operate concurrently if they hit different stripes
 * - Throughput scales nearly linearly with stripe count (until memory bus saturation)
 * 
 * MEMORY ORDERING:
 * - Lock acquisition provides acquire semantics (see all prior writes)
 * - Lock release provides release semantics (writes visible to next acquirer)
 * - Within a stripe, operations are serialized (total order per stripe)
 * - Across stripes, no ordering guarantee (which is fine for independent keys)
 * 
 * PITFALLS:
 * 1. Too few stripes = contention; too many = memory waste + cache pollution
 * 2. Cross-stripe operations (e.g., size(), clear()) need ALL locks → expensive
 * 3. Resize requires ALL locks (ConcurrentHashMap avoids this with incremental resize)
 * 4. Hash function quality matters: poor distribution = hot stripes
 * 5. Must not hold multiple stripe locks (deadlock risk unless ordered)
 */
public class Problem69_LockStripingHashMap<K, V> {

    private static final int DEFAULT_STRIPES = 16;
    private static final int DEFAULT_BUCKETS_PER_STRIPE = 64;

    // ==================== INTERNAL STRUCTURES ====================
    static class Entry<K, V> {
        final K key;
        volatile V value;
        final int hash;
        Entry<K, V> next;

        Entry(K key, V value, int hash, Entry<K, V> next) {
            this.key = key;
            this.value = value;
            this.hash = hash;
            this.next = next;
        }
    }

    private final int numStripes;
    private final ReentrantLock[] locks;
    @SuppressWarnings("unchecked")
    private volatile Entry<K, V>[] table; // [bucket] -> chain
    private final AtomicInteger size = new AtomicInteger(0);
    private final int totalBuckets;

    @SuppressWarnings("unchecked")
    public Problem69_LockStripingHashMap(int numStripes) {
        this.numStripes = numStripes;
        this.totalBuckets = numStripes * DEFAULT_BUCKETS_PER_STRIPE;
        this.locks = new ReentrantLock[numStripes];
        this.table = new Entry[totalBuckets];

        for (int i = 0; i < numStripes; i++) {
            locks[i] = new ReentrantLock();
        }
    }

    public Problem69_LockStripingHashMap() {
        this(DEFAULT_STRIPES);
    }

    /** Determine which stripe a hash belongs to */
    private int stripeFor(int hash) {
        return Math.abs(hash % numStripes);
    }

    /** Determine which bucket a hash belongs to */
    private int bucketFor(int hash) {
        return Math.abs(hash % totalBuckets);
    }

    private int hash(K key) {
        int h = key.hashCode();
        // Spread bits (like ConcurrentHashMap)
        return h ^ (h >>> 16);
    }

    public V put(K key, V value) {
        int h = hash(key);
        int stripe = stripeFor(h);
        int bucket = bucketFor(h);

        locks[stripe].lock();
        try {
            Entry<K, V> head = (Entry<K, V>) table[bucket];
            // Search for existing key
            for (Entry<K, V> e = head; e != null; e = e.next) {
                if (e.hash == h && e.key.equals(key)) {
                    V old = e.value;
                    e.value = value;
                    return old;
                }
            }
            // Insert at head
            table[bucket] = new Entry<>(key, value, h, head);
            size.incrementAndGet();
            return null;
        } finally {
            locks[stripe].unlock();
        }
    }

    public V get(K key) {
        int h = hash(key);
        int stripe = stripeFor(h);
        int bucket = bucketFor(h);

        locks[stripe].lock();
        try {
            for (Entry<K, V> e = table[bucket]; e != null; e = e.next) {
                if (e.hash == h && e.key.equals(key)) {
                    return e.value;
                }
            }
            return null;
        } finally {
            locks[stripe].unlock();
        }
    }

    public V remove(K key) {
        int h = hash(key);
        int stripe = stripeFor(h);
        int bucket = bucketFor(h);

        locks[stripe].lock();
        try {
            Entry<K, V> prev = null;
            Entry<K, V> e = table[bucket];
            while (e != null) {
                if (e.hash == h && e.key.equals(key)) {
                    if (prev == null) table[bucket] = e.next;
                    else prev.next = e.next;
                    size.decrementAndGet();
                    return e.value;
                }
                prev = e;
                e = e.next;
            }
            return null;
        } finally {
            locks[stripe].unlock();
        }
    }

    /** Size is approximate (not holding all locks) */
    public int size() { return size.get(); }

    /** Exact size requires all locks - expensive! */
    public int exactSize() {
        for (ReentrantLock lock : locks) lock.lock();
        try {
            return size.get();
        } finally {
            for (ReentrantLock lock : locks) lock.unlock();
        }
    }

    // ==================== STRESS TEST + COMPARISON ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Lock Striping HashMap ===\n");

        int numThreads = 8;
        int opsPerThread = 500_000;

        // Test 1: Lock-striped map
        Problem69_LockStripingHashMap<Integer, String> stripedMap = new Problem69_LockStripingHashMap<>(32);
        long stripedTime = benchmark("Lock-Striped (32 stripes)", stripedMap, numThreads, opsPerThread);

        // Test 2: Single-lock map for comparison
        Problem69_LockStripingHashMap<Integer, String> singleLock = new Problem69_LockStripingHashMap<>(1);
        long singleTime = benchmark("Single-Lock (1 stripe)", singleLock, numThreads, opsPerThread);

        System.out.println("\n--- Comparison ---");
        System.out.println("Speedup from lock striping: " + String.format("%.2fx", (double)singleTime / stripedTime));
        System.out.println("\nKey insight: ConcurrentHashMap uses exactly this technique.");
        System.out.println("More stripes = more parallelism (up to memory bus bandwidth limit).");
        System.out.println("Cross-stripe operations (size, clear, resize) are expensive.");
    }

    private static long benchmark(String name, Problem69_LockStripingHashMap<Integer, String> map,
                                   int numThreads, int opsPerThread) throws InterruptedException {
        AtomicInteger totalOps = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < opsPerThread; i++) {
                    int key = rng.nextInt(50000);
                    int op = rng.nextInt(10);
                    if (op < 4) map.put(key, "v" + key);
                    else if (op < 8) map.get(key);
                    else map.remove(key);
                    totalOps.incrementAndGet();
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println(name + ":");
        System.out.println("  Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("  Throughput: " + (totalOps.get() * 1_000_000_000L / elapsed) + " ops/sec");
        System.out.println("  Final size: " + map.size());
        return elapsed;
    }
}
