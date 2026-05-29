import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Problem 61: Multi-Version Concurrency Control (MVCC)
 * 
 * REAL-WORLD USAGE:
 * - PostgreSQL: all transactions see a consistent snapshot (MVCC core)
 * - MySQL InnoDB: uses undo log for multi-version reads
 * - Oracle: read consistency via undo tablespace
 * - CockroachDB, Spanner: distributed MVCC with timestamps
 * - Git: every commit is a version, branches see different versions
 * 
 * KEY CONCEPTS:
 * - Each write creates a NEW VERSION (old versions are kept)
 * - Readers see a consistent snapshot at their start timestamp
 * - Writers don't block readers, readers don't block writers
 * - Garbage collection removes versions no longer visible to any transaction
 * 
 * ISOLATION LEVELS:
 * - Read Committed: see latest committed version at time of each read
 * - Snapshot Isolation: see versions as of transaction start time
 * - Serializable: snapshot + write-write conflict detection
 * 
 * MEMORY ORDERING:
 * - Version chain must be consistently ordered by timestamp
 * - Commit timestamp assignment is the linearization point
 * - Global timestamp counter uses AtomicLong (sequential consistency)
 */
public class Problem61_MultiVersionConcurrencyControl {

    // ==================== VERSION CHAIN ====================
    static class Version<T> {
        final T value;
        final long writeTimestamp;  // When this version was created
        final long txId;            // Transaction that created it
        volatile boolean committed; // Is this version committed?
        Version<T> prev;            // Previous version (older)

        Version(T value, long writeTs, long txId) {
            this.value = value;
            this.writeTimestamp = writeTs;
            this.txId = txId;
            this.committed = false;
        }
    }

    // ==================== MVCC CELL (single key-value) ====================
    static class MVCCCell<T> {
        private volatile Version<T> latest; // Head of version chain
        private final ReentrantLock writeLock = new ReentrantLock();

        /**
         * READ: Find the latest committed version visible to the given timestamp.
         * Walks the version chain backward until finding a committed version <= readTs.
         * This NEVER blocks, even if a write is in progress.
         */
        public T read(long readTimestamp) {
            Version<T> v = latest;
            while (v != null) {
                if (v.committed && v.writeTimestamp <= readTimestamp) {
                    return v.value;
                }
                v = v.prev;
            }
            return null; // No visible version
        }

        /**
         * WRITE: Create a new version. Returns false if write-write conflict.
         */
        public boolean write(T value, long writeTimestamp, long txId) {
            writeLock.lock();
            try {
                // Write-write conflict detection:
                // If latest uncommitted version is from a different tx, conflict
                Version<T> cur = latest;
                if (cur != null && !cur.committed && cur.txId != txId) {
                    return false; // Conflict - another tx has uncommitted write
                }

                Version<T> newVersion = new Version<>(value, writeTimestamp, txId);
                newVersion.prev = latest;
                latest = newVersion;
                return true;
            } finally {
                writeLock.unlock();
            }
        }

        /** Mark all versions from txId as committed */
        public void commit(long txId) {
            Version<T> v = latest;
            while (v != null) {
                if (v.txId == txId) v.committed = true;
                v = v.prev;
            }
        }

        /** Abort: remove uncommitted versions from txId */
        public void abort(long txId) {
            writeLock.lock();
            try {
                // Remove versions from this tx
                while (latest != null && latest.txId == txId && !latest.committed) {
                    latest = latest.prev;
                }
            } finally {
                writeLock.unlock();
            }
        }

        /** GC: remove versions not visible to any active transaction */
        public int gc(long oldestActiveTimestamp) {
            int removed = 0;
            Version<T> v = latest;
            Version<T> prev = null;
            boolean foundVisible = false;
            while (v != null) {
                if (v.committed && v.writeTimestamp < oldestActiveTimestamp && foundVisible) {
                    // This version is no longer needed
                    if (prev != null) prev.prev = null;
                    removed++;
                    break; // Truncate chain
                }
                if (v.committed) foundVisible = true;
                prev = v;
                v = v.prev;
            }
            return removed;
        }
    }

    // ==================== MVCC DATABASE ====================
    static class MVCCDatabase {
        private final ConcurrentHashMap<String, MVCCCell<String>> store = new ConcurrentHashMap<>();
        private final AtomicLong timestampCounter = new AtomicLong(0);
        private final AtomicLong txIdCounter = new AtomicLong(0);
        private final Set<Long> activeTxTimestamps = ConcurrentHashMap.newKeySet();

        public long beginTransaction() {
            long ts = timestampCounter.incrementAndGet();
            activeTxTimestamps.add(ts);
            return ts; // This is both the txId and the read timestamp
        }

        public String read(long txTs, String key) {
            MVCCCell<String> cell = store.get(key);
            if (cell == null) return null;
            return cell.read(txTs); // See snapshot as of txTs
        }

        public boolean write(long txTs, String key, String value) {
            store.computeIfAbsent(key, k -> new MVCCCell<>());
            return store.get(key).write(value, txTs, txTs);
        }

        public void commit(long txTs) {
            for (MVCCCell<String> cell : store.values()) {
                cell.commit(txTs);
            }
            activeTxTimestamps.remove(txTs);
        }

        public void abort(long txTs) {
            for (MVCCCell<String> cell : store.values()) {
                cell.abort(txTs);
            }
            activeTxTimestamps.remove(txTs);
        }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Multi-Version Concurrency Control (MVCC) ===\n");

        // Demo: snapshot isolation
        System.out.println("--- Snapshot Isolation Demo ---");
        MVCCDatabase db = new MVCCDatabase();

        // Tx1: write initial data
        long tx1 = db.beginTransaction();
        db.write(tx1, "balance", "1000");
        db.commit(tx1);

        // Tx2: start reading (snapshot at this point)
        long tx2 = db.beginTransaction();
        System.out.println("Tx2 reads balance: " + db.read(tx2, "balance"));

        // Tx3: update balance (after tx2 started)
        long tx3 = db.beginTransaction();
        db.write(tx3, "balance", "500");
        db.commit(tx3);

        // Tx2 still sees old value (snapshot isolation!)
        System.out.println("Tx2 reads balance AFTER tx3 committed: " + db.read(tx2, "balance"));
        System.out.println("(Should still be 1000 - snapshot isolation)\n");
        db.commit(tx2);

        // New tx sees updated value
        long tx4 = db.beginTransaction();
        System.out.println("Tx4 reads balance: " + db.read(tx4, "balance") + " (sees 500)");
        db.commit(tx4);

        // Stress test
        System.out.println("\n--- Concurrent MVCC Stress Test ---");
        MVCCDatabase stressDb = new MVCCDatabase();
        int numThreads = 8;
        int txPerThread = 50_000;
        AtomicInteger commits = new AtomicInteger(0);
        AtomicInteger aborts = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        // Pre-populate
        long init = stressDb.beginTransaction();
        for (int i = 0; i < 100; i++) {
            stressDb.write(init, "key-" + i, "0");
        }
        stressDb.commit(init);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < txPerThread; i++) {
                    long tx = stressDb.beginTransaction();
                    String key = "key-" + rng.nextInt(100);
                    String val = stressDb.read(tx, key);
                    int newVal = (val == null ? 0 : Integer.parseInt(val)) + 1;
                    if (stressDb.write(tx, key, String.valueOf(newVal))) {
                        stressDb.commit(tx);
                        commits.incrementAndGet();
                    } else {
                        stressDb.abort(tx);
                        aborts.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("Threads: " + numThreads + ", Tx/thread: " + txPerThread);
        System.out.println("Commits: " + commits.get() + ", Aborts: " + aborts.get());
        System.out.println("Abort rate: " + (aborts.get() * 100 / (commits.get() + aborts.get())) + "%");
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (commits.get() * 1_000_000_000L / elapsed) + " tx/sec");
        System.out.println("\nKey insight: Readers NEVER block writers. Writers NEVER block readers.");
        System.out.println("This is how PostgreSQL handles thousands of concurrent queries.");
    }
}
