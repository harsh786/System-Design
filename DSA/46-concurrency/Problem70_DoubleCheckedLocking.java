import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;

/**
 * Problem 70: Double-Checked Locking with Memory Barriers
 * 
 * REAL-WORLD USAGE:
 * - Singleton initialization in frameworks (Spring beans, Android)
 * - Lazy initialization of expensive resources (DB connections, caches)
 * - ClassLoader delegation in JVM
 * - Plugin/driver loading systems
 * 
 * THE CLASSIC BUG (pre-Java 5):
 *   if (instance == null) {           // First check (no lock)
 *       synchronized(lock) {
 *           if (instance == null) {   // Second check (with lock)
 *               instance = new Foo(); // BUG: can be reordered!
 *           }
 *       }
 *   }
 * 
 * WHY IT WAS BROKEN:
 * - "instance = new Foo()" is 3 steps: allocate, construct, assign reference
 * - Without volatile, CPU/compiler can reorder: allocate → assign → construct
 * - Thread B sees non-null instance but reads uninitialized fields!
 * - This is called "publishing a partially constructed object"
 * 
 * THE FIX (Java 5+):
 * - Declare instance as VOLATILE
 * - Volatile write has release semantics: all prior writes (construction) are
 *   visible before the reference assignment
 * - Volatile read has acquire semantics: subsequent reads see all writes before
 *   the volatile write
 * 
 * MEMORY ORDERING (Java Memory Model JSR-133):
 * - volatile write → StoreStore + StoreLoad barriers
 * - volatile read → LoadLoad + LoadStore barriers
 * - These barriers prevent the construction from being reordered after assignment
 * 
 * ALTERNATIVES (no double-checked locking needed):
 * 1. Initialization-on-demand holder idiom (preferred for singletons)
 * 2. enum singleton (safest)
 * 3. AtomicReference + compareAndSet (lock-free lazy init)
 * 
 * PITFALLS:
 * 1. MUST use volatile (or final fields) for this to be safe in Java
 * 2. In C++, need std::atomic with memory_order_acquire/release
 * 3. Final fields have special semantics: visible after constructor completes
 *    even without volatile (but only if 'this' doesn't escape during construction)
 * 4. Don't use in performance-critical paths if the branch prediction penalty matters
 */
public class Problem70_DoubleCheckedLocking {

    // ==================== PATTERN 1: Classic DCL (CORRECT with volatile) ====================
    static class ExpensiveResource {
        private final long[] data; // Simulate expensive initialization
        private final String name;
        private final long createdAt;

        ExpensiveResource(String name) {
            this.name = name;
            this.data = new long[1000];
            Arrays.fill(data, 42L); // Simulate work
            this.createdAt = System.nanoTime();
            // Without volatile on the reference, another thread could see
            // this object with data = null or partially filled!
        }

        boolean isValid() {
            return data != null && data.length == 1000 && data[0] == 42L && name != null;
        }
    }

    static class DoubleCheckedSingleton {
        // VOLATILE is the key! Without it, DCL is broken.
        private static volatile ExpensiveResource instance;

        public static ExpensiveResource getInstance() {
            ExpensiveResource local = instance; // Single volatile read (optimization)
            if (local == null) {                // First check: avoid lock if already initialized
                synchronized (DoubleCheckedSingleton.class) {
                    local = instance;
                    if (local == null) {        // Second check: inside lock
                        instance = local = new ExpensiveResource("singleton");
                    }
                }
            }
            return local;
        }
    }

    // ==================== PATTERN 2: Holder Idiom (NO DCL needed) ====================
    static class HolderIdiomSingleton {
        // Class is not loaded until getInstance() is called
        // Class loading is thread-safe by JVM spec → no synchronization needed
        private static class Holder {
            static final ExpensiveResource INSTANCE = new ExpensiveResource("holder");
        }

        public static ExpensiveResource getInstance() {
            return Holder.INSTANCE; // Triggers class loading on first call
        }
    }

    // ==================== PATTERN 3: CAS-based Lazy Init (Lock-Free) ====================
    static class CASLazyInit<T> {
        private final AtomicReference<T> ref = new AtomicReference<>(null);
        private final Callable<T> factory;

        CASLazyInit(Callable<T> factory) { this.factory = factory; }

        public T get() {
            T val = ref.get();
            if (val != null) return val;

            try {
                T newVal = factory.call();
                // CAS: only one thread's creation wins
                if (ref.compareAndSet(null, newVal)) {
                    return newVal;
                }
                // Another thread beat us - use their instance
                return ref.get();
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }
    }

    // ==================== PATTERN 4: DCL for lazy Map values ====================
    static class LazyCache<K, V> {
        private final ConcurrentHashMap<K, V> cache = new ConcurrentHashMap<>();
        private final ConcurrentHashMap<K, Object> locks = new ConcurrentHashMap<>();

        /**
         * Get or compute with DCL pattern.
         * ConcurrentHashMap.computeIfAbsent is simpler but holds the bucket lock
         * during computation (bad for expensive computations).
         */
        public V getOrCompute(K key, Callable<V> computation) throws Exception {
            V value = cache.get(key); // First check (no lock)
            if (value != null) return value;

            Object lock = locks.computeIfAbsent(key, k -> new Object());
            synchronized (lock) {
                value = cache.get(key); // Second check (with lock)
                if (value != null) return value;

                value = computation.call();
                cache.put(key, value); // ConcurrentHashMap.put is volatile write
                return value;
            }
        }

        public int size() { return cache.size(); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Double-Checked Locking with Memory Barriers ===\n");

        // Test 1: DCL Singleton - verify single initialization under contention
        System.out.println("--- DCL Singleton Test ---");
        int numThreads = 16;
        Set<Integer> identityHashes = ConcurrentHashMap.newKeySet();
        AtomicInteger invalidInstances = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < 100_000; i++) {
                    ExpensiveResource r = DoubleCheckedSingleton.getInstance();
                    identityHashes.add(System.identityHashCode(r));
                    if (!r.isValid()) {
                        invalidInstances.incrementAndGet(); // Would detect partially constructed object
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        startLatch.countDown();
        doneLatch.await();

        System.out.println("Threads: " + numThreads + ", accesses per thread: 100,000");
        System.out.println("Unique instances created: " + identityHashes.size() + " (should be 1)");
        System.out.println("Invalid (partially constructed) reads: " + invalidInstances.get() + " (should be 0)");

        // Test 2: Lazy Cache with DCL
        System.out.println("\n--- Lazy Cache (DCL per key) ---");
        LazyCache<String, String> cache = new LazyCache<>();
        AtomicInteger computations = new AtomicInteger(0);
        CountDownLatch startLatch2 = new CountDownLatch(1);
        CountDownLatch doneLatch2 = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch2.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < 100_000; i++) {
                    String key = "key-" + rng.nextInt(100);
                    try {
                        cache.getOrCompute(key, () -> {
                            computations.incrementAndGet();
                            return "computed-" + key;
                        });
                    } catch (Exception e) {}
                }
                doneLatch2.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch2.countDown();
        doneLatch2.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("Keys: 100, Threads: " + numThreads + ", Ops: " + (numThreads * 100_000));
        System.out.println("Actual computations: " + computations.get() + " (should be ~100, one per key)");
        System.out.println("Cache size: " + cache.size());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");

        // Test 3: CAS-based lazy init
        System.out.println("\n--- CAS-based Lazy Init ---");
        AtomicInteger casCreations = new AtomicInteger(0);
        CASLazyInit<String> casLazy = new CASLazyInit<>(() -> {
            casCreations.incrementAndGet();
            return "expensive-value";
        });

        CountDownLatch startLatch3 = new CountDownLatch(1);
        CountDownLatch doneLatch3 = new CountDownLatch(numThreads);
        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch3.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < 100_000; i++) casLazy.get();
                doneLatch3.countDown();
            }).start();
        }
        startLatch3.countDown();
        doneLatch3.await();
        // Note: CAS-based may create multiple instances (but only one wins)
        System.out.println("CAS creations: " + casCreations.get() + " (may be > 1, but only 1 is used)");
        System.out.println("Value: " + casLazy.get());

        System.out.println("\n--- Summary ---");
        System.out.println("✓ DCL requires volatile (Java 5+) or atomic (C++) to be safe");
        System.out.println("✓ Holder idiom is simpler and preferred for singletons");
        System.out.println("✓ Without volatile, you get 'partially constructed object' bug");
        System.out.println("✓ The memory barrier on volatile write ensures construction completes");
        System.out.println("  BEFORE the reference becomes visible to other threads");
    }
}
