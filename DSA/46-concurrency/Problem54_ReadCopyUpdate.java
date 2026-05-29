import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.CountDownLatch;
import java.util.*;

/**
 * Problem 54: Read-Copy-Update (RCU) Pattern
 * 
 * REAL-WORLD USAGE:
 * - Linux kernel: routing tables, firewall rules, module lists
 * - Configuration management (read config without locks)
 * - DNS caches, routing caches
 * - Any read-dominated data structure (99%+ reads)
 * 
 * KEY CONCEPTS:
 * - Readers access shared data with ZERO synchronization overhead
 * - Writers create a COPY, modify the copy, then atomically swap the pointer
 * - Old version is kept alive until all readers that might reference it are done
 *   (grace period / quiescent state detection)
 * 
 * MEMORY ORDERING:
 * - AtomicReference.get() provides acquire semantics (sees all writes before publication)
 * - AtomicReference.set() provides release semantics (prior writes visible)
 * - Readers see a consistent snapshot (either old or new, never partial)
 * 
 * TRADE-OFFS:
 * - Reads: O(1), zero contention, no cache-line bouncing
 * - Writes: O(n) - must copy entire structure
 * - Memory: temporarily holds old + new version (2x during grace period)
 * 
 * PITFALLS:
 * 1. Writers must serialize among themselves (only ONE writer at a time)
 * 2. Grace period management is complex in practice (epoch-based reclamation)
 * 3. Copy cost grows with data size - not suitable for huge mutable structures
 * 4. Readers must not hold references to internal nodes across read operations
 */
public class Problem54_ReadCopyUpdate {

    // ==================== RCU-PROTECTED ROUTING TABLE ====================
    /**
     * Simulates a routing table that is read millions of times per second
     * but updated rarely (config changes, new routes learned).
     */
    static class RCURoutingTable {
        // The shared pointer - readers just dereference this
        private final AtomicReference<Map<String, String>> routeMap;
        // Writer lock (only one writer at a time)
        private final Object writerLock = new Object();

        RCURoutingTable() {
            routeMap = new AtomicReference<>(Collections.unmodifiableMap(new HashMap<>()));
        }

        /**
         * READ: Zero overhead - just a volatile read of the reference.
         * No lock, no CAS, no memory barrier beyond the volatile read.
         * Returns a consistent snapshot - even if a write happens during iteration,
         * the reader sees either the complete old map or the complete new map.
         */
        public String lookup(String destination) {
            // This is the "read" in RCU - just follow the pointer
            Map<String, String> current = routeMap.get();
            return current.get(destination);
        }

        /**
         * WRITE: Copy-on-write. Expensive but rare.
         * 1. Copy the current map
         * 2. Modify the copy
         * 3. Atomically publish the new map
         * 4. Old map is reclaimed when no readers reference it (GC handles grace period in Java)
         */
        public void updateRoute(String destination, String nextHop) {
            synchronized (writerLock) { // Serialize writers
                // COPY
                Map<String, String> current = routeMap.get();
                Map<String, String> newMap = new HashMap<>(current);
                // UPDATE the copy
                newMap.put(destination, nextHop);
                // PUBLISH atomically (the "rcu_assign_pointer")
                routeMap.set(Collections.unmodifiableMap(newMap));
                // In Java, GC handles grace period - old map lives until readers are done
                // In C/kernel, you'd call synchronize_rcu() or use call_rcu() for deferred free
            }
        }

        public void removeRoute(String destination) {
            synchronized (writerLock) {
                Map<String, String> current = routeMap.get();
                Map<String, String> newMap = new HashMap<>(current);
                newMap.remove(destination);
                routeMap.set(Collections.unmodifiableMap(newMap));
            }
        }

        public int size() {
            return routeMap.get().size();
        }
    }

    // ==================== RCU-PROTECTED CONFIG (Immutable snapshots) ====================
    static class RCUConfig {
        // Immutable configuration snapshot
        static class ConfigSnapshot {
            final Map<String, String> properties;
            final long version;

            ConfigSnapshot(Map<String, String> properties, long version) {
                this.properties = Collections.unmodifiableMap(new HashMap<>(properties));
                this.version = version;
            }
        }

        private final AtomicReference<ConfigSnapshot> config;
        private long versionCounter = 0;

        RCUConfig() {
            config = new AtomicReference<>(new ConfigSnapshot(new HashMap<>(), 0));
        }

        // Fast read - no synchronization
        public ConfigSnapshot getConfig() {
            return config.get(); // Single volatile read
        }

        // Slow write - copy and publish
        public synchronized void setProperty(String key, String value) {
            ConfigSnapshot current = config.get();
            Map<String, String> newProps = new HashMap<>(current.properties);
            newProps.put(key, value);
            config.set(new ConfigSnapshot(newProps, ++versionCounter));
        }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Read-Copy-Update (RCU) Pattern Stress Test ===\n");

        RCURoutingTable table = new RCURoutingTable();
        // Pre-populate
        for (int i = 0; i < 1000; i++) {
            table.updateRoute("10.0." + (i / 256) + "." + (i % 256), "gateway-" + (i % 10));
        }

        int numReaders = 6;
        int numWriters = 2;
        int readsPerThread = 5_000_000;
        int writesPerThread = 10_000;
        AtomicInteger totalReads = new AtomicInteger(0);
        AtomicInteger totalWrites = new AtomicInteger(0);
        AtomicInteger nullReads = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numReaders + numWriters);

        // Readers - zero synchronization overhead
        for (int r = 0; r < numReaders; r++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < readsPerThread; i++) {
                    String key = "10.0." + rng.nextInt(4) + "." + rng.nextInt(256);
                    String result = table.lookup(key);
                    if (result == null) nullReads.incrementAndGet();
                    totalReads.incrementAndGet();
                }
                doneLatch.countDown();
            }).start();
        }

        // Writers - copy-on-write, serialized
        for (int w = 0; w < numWriters; w++) {
            final int wid = w;
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < writesPerThread; i++) {
                    String key = "10.0." + rng.nextInt(4) + "." + rng.nextInt(256);
                    table.updateRoute(key, "gw-" + wid + "-" + i);
                    totalWrites.incrementAndGet();
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("Readers: " + numReaders + ", Writers: " + numWriters);
        System.out.println("Total reads: " + totalReads.get() + " (" + readsPerThread + "/reader)");
        System.out.println("Total writes: " + totalWrites.get());
        System.out.println("Read/Write ratio: " + (totalReads.get() / totalWrites.get()) + ":1");
        System.out.println("Null reads (key not found): " + nullReads.get());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Read throughput: " + (totalReads.get() * 1_000_000_000L / elapsed) + " reads/sec");
        System.out.println("Final table size: " + table.size());
        System.out.println("\nKey insight: Readers NEVER block, even during writes.");
        System.out.println("This is why Linux kernel uses RCU for routing tables and firewall rules.");
    }
}
