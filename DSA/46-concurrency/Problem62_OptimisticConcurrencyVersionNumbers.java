import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Problem 62: Optimistic Concurrency with Version Numbers
 * 
 * REAL-WORLD USAGE:
 * - HTTP ETags (If-Match header for conditional updates)
 * - DynamoDB conditional writes (ConditionExpression on version)
 * - JPA/Hibernate @Version annotation
 * - CAS in distributed caches (Redis WATCH/MULTI)
 * - Kubernetes resource version (optimistic locking on etcd)
 * 
 * KEY CONCEPTS:
 * - Read: get value AND its version number
 * - Write: "update value WHERE version = expected_version"
 * - If version changed between read and write → conflict → retry
 * - No locks held during computation (optimistic = assume no conflict)
 * 
 * VS PESSIMISTIC (locks):
 * - Optimistic: high throughput when conflicts are rare
 * - Pessimistic: better when conflicts are frequent (avoids wasted work)
 * 
 * MEMORY ORDERING:
 * - Version number update must be atomic with value update
 * - CAS on version provides the linearization point
 * - All reads of value after successful CAS see the new value (happens-before)
 */
public class Problem62_OptimisticConcurrencyVersionNumbers {

    // ==================== VERSIONED RECORD ====================
    static class VersionedRecord<T> {
        private volatile T value;
        private final AtomicLong version = new AtomicLong(0);
        private final ReentrantLock lock = new ReentrantLock(); // Only for write serialization

        VersionedRecord(T initial) { this.value = initial; }

        public static class ReadResult<T> {
            public final T value;
            public final long version;
            ReadResult(T value, long version) { this.value = value; this.version = version; }
        }

        /** Read value and version atomically */
        public ReadResult<T> read() {
            long v = version.get();
            T val = value;
            // Validate version didn't change during read
            if (version.get() != v) {
                // Concurrent write - retry
                return read();
            }
            return new ReadResult<>(val, v);
        }

        /**
         * Conditional write: only succeeds if current version matches expected.
         * Returns new version on success, -1 on conflict.
         */
        public long compareAndUpdate(T newValue, long expectedVersion) {
            lock.lock();
            try {
                if (version.get() != expectedVersion) {
                    return -1; // Conflict!
                }
                value = newValue;
                return version.incrementAndGet();
            } finally {
                lock.unlock();
            }
        }

        public long getVersion() { return version.get(); }
    }

    // ==================== OPTIMISTIC KEY-VALUE STORE ====================
    static class OptimisticStore {
        private final ConcurrentHashMap<String, VersionedRecord<String>> store = new ConcurrentHashMap<>();

        public void put(String key, String value) {
            store.computeIfAbsent(key, k -> new VersionedRecord<>(""));
            VersionedRecord<String> record = store.get(key);
            // Retry loop for optimistic update
            while (true) {
                var current = record.read();
                long newVersion = record.compareAndUpdate(value, current.version);
                if (newVersion >= 0) return; // Success
            }
        }

        public VersionedRecord.ReadResult<String> get(String key) {
            VersionedRecord<String> record = store.get(key);
            return record == null ? null : record.read();
        }

        /**
         * Read-modify-write with optimistic concurrency.
         * Example: increment a counter stored as string.
         */
        public boolean incrementIfVersion(String key, long expectedVersion) {
            VersionedRecord<String> record = store.get(key);
            if (record == null) return false;
            var current = record.read();
            if (current.version != expectedVersion) return false;
            int newVal = Integer.parseInt(current.value) + 1;
            return record.compareAndUpdate(String.valueOf(newVal), expectedVersion) >= 0;
        }

        /** Optimistic read-modify-write with automatic retry */
        public int incrementWithRetry(String key) {
            VersionedRecord<String> record = store.computeIfAbsent(key, k -> new VersionedRecord<>("0"));
            while (true) {
                var current = record.read();
                int newVal = Integer.parseInt(current.value) + 1;
                long result = record.compareAndUpdate(String.valueOf(newVal), current.version);
                if (result >= 0) return newVal;
                // Conflict - retry (another thread updated between our read and write)
            }
        }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Optimistic Concurrency with Version Numbers ===\n");

        // Demo: conflict detection
        System.out.println("--- Conflict Detection Demo ---");
        VersionedRecord<String> record = new VersionedRecord<>("initial");
        var r1 = record.read();
        System.out.println("Thread A reads: '" + r1.value + "' at version " + r1.version);

        // Thread B updates
        long newVer = record.compareAndUpdate("updated-by-B", r1.version);
        System.out.println("Thread B updates to version " + newVer);

        // Thread A tries to update with stale version - CONFLICT
        long result = record.compareAndUpdate("updated-by-A", r1.version);
        System.out.println("Thread A update result: " + (result >= 0 ? "success" : "CONFLICT (expected)"));

        // Stress test: concurrent counter increment
        System.out.println("\n--- Concurrent Counter Increment ---");
        OptimisticStore store = new OptimisticStore();
        store.put("counter", "0");
        int numThreads = 8;
        int incsPerThread = 100_000;
        AtomicInteger retries = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                VersionedRecord<String> rec = store.store.get("counter");
                for (int i = 0; i < incsPerThread; i++) {
                    while (true) {
                        var current = rec.read();
                        int newVal = Integer.parseInt(current.value) + 1;
                        if (rec.compareAndUpdate(String.valueOf(newVal), current.version) >= 0) {
                            break;
                        }
                        retries.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        var finalVal = store.get("counter");
        int expected = numThreads * incsPerThread;
        System.out.println("Threads: " + numThreads + ", Increments/thread: " + incsPerThread);
        System.out.println("Expected final value: " + expected);
        System.out.println("Actual final value: " + finalVal.value);
        System.out.println("Correct: " + (Integer.parseInt(finalVal.value) == expected));
        System.out.println("Final version: " + finalVal.version);
        System.out.println("Total retries (conflicts): " + retries.get());
        System.out.println("Conflict rate: " + (retries.get() * 100 / (expected + retries.get())) + "%");
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("\nKey insight: Same pattern as HTTP ETags, DynamoDB conditional writes,");
        System.out.println("and Kubernetes resource versions. No locks held during computation!");
    }
}
