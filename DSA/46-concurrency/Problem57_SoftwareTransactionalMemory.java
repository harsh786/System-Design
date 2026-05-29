import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Problem 57: Software Transactional Memory (STM Concept)
 * 
 * REAL-WORLD USAGE:
 * - Clojure's Ref/STM system (core language feature)
 * - Haskell's STM (GHC runtime)
 * - Database MVCC (PostgreSQL, MySQL InnoDB) uses similar concepts
 * - Intel TSX (Hardware Transactional Memory) at CPU level
 * 
 * KEY CONCEPTS:
 * - Transactions: group of reads/writes that appear atomic
 * - Optimistic concurrency: execute speculatively, validate at commit
 * - Read set: all TVar values read during transaction
 * - Write set: all TVar values written during transaction
 * - Commit: validate read-set hasn't changed, then apply write-set atomically
 * - Retry: if validation fails, restart the transaction
 * 
 * MEMORY ORDERING:
 * - Each TVar has a version number (incremented on write)
 * - At commit time: lock all write-set TVars, validate read-set versions,
 *   apply writes, unlock - this is the linearization point
 * - Serializable isolation: transactions appear to execute one at a time
 * 
 * PITFALLS:
 * 1. Long transactions have high abort rate (they read more, more likely to conflict)
 * 2. Side effects in transactions are DANGEROUS (transaction may retry!)
 *    Never do I/O, print, or modify non-TVar state inside a transaction
 * 3. Livelock: two transactions repeatedly conflict and retry forever
 * 4. Performance degrades under high contention (many aborts)
 */
public class Problem57_SoftwareTransactionalMemory {

    // ==================== TRANSACTIONAL VARIABLE ====================
    static class TVar<T> {
        private volatile T value;
        private final AtomicLong version = new AtomicLong(0);
        private final ReentrantLock lock = new ReentrantLock();

        TVar(T initial) { this.value = initial; }

        T read() { return value; }
        long getVersion() { return version.get(); }
        void write(T val) { value = val; version.incrementAndGet(); }
        void lock() { lock.lock(); }
        void unlock() { lock.unlock(); }
        boolean tryLock() { return lock.tryLock(); }
    }

    // ==================== TRANSACTION ====================
    static class Transaction {
        private final Map<TVar<?>, Long> readSet = new HashMap<>();  // TVar -> version read
        private final Map<TVar<?>, Object> writeSet = new HashMap<>(); // TVar -> new value
        private boolean aborted = false;

        @SuppressWarnings("unchecked")
        public <T> T read(TVar<T> tvar) {
            if (aborted) throw new TransactionAbortedException();
            // Check write set first (read-your-own-writes)
            if (writeSet.containsKey(tvar)) {
                return (T) writeSet.get(tvar);
            }
            // Read from TVar and record version
            T value = tvar.read();
            readSet.put(tvar, tvar.getVersion());
            return value;
        }

        public <T> void write(TVar<T> tvar, T value) {
            if (aborted) throw new TransactionAbortedException();
            writeSet.put(tvar, value);
            // Also record in read set if not already there
            if (!readSet.containsKey(tvar)) {
                readSet.put(tvar, tvar.getVersion());
            }
        }

        @SuppressWarnings("unchecked")
        public boolean commit() {
            // Phase 1: Lock all TVars in write set (ordered to prevent deadlock)
            List<TVar<?>> lockedVars = new ArrayList<>(writeSet.keySet());
            // Sort by identity hash to establish consistent lock ordering
            lockedVars.sort(Comparator.comparingInt(System::identityHashCode));

            for (TVar<?> tvar : lockedVars) {
                tvar.lock();
            }

            try {
                // Phase 2: Validate read set (have versions changed?)
                for (Map.Entry<TVar<?>, Long> entry : readSet.entrySet()) {
                    TVar<?> tvar = entry.getKey();
                    long expectedVersion = entry.getValue();
                    if (tvar.getVersion() != expectedVersion) {
                        aborted = true;
                        return false; // Conflict detected - abort
                    }
                }

                // Phase 3: Apply writes
                for (Map.Entry<TVar<?>, Object> entry : writeSet.entrySet()) {
                    @SuppressWarnings("rawtypes")
                    TVar tvar = entry.getKey();
                    tvar.write(entry.getValue());
                }
                return true;
            } finally {
                // Phase 4: Unlock all
                for (TVar<?> tvar : lockedVars) {
                    tvar.unlock();
                }
            }
        }
    }

    static class TransactionAbortedException extends RuntimeException {}

    // ==================== STM RUNTIME ====================
    interface TransactionBody<T> {
        T execute(Transaction tx);
    }

    static <T> T atomic(TransactionBody<T> body) {
        int maxRetries = 100;
        for (int attempt = 0; attempt < maxRetries; attempt++) {
            Transaction tx = new Transaction();
            try {
                T result = body.execute(tx);
                if (tx.commit()) {
                    return result;
                }
                // Commit failed - retry with backoff
                if (attempt > 10) {
                    Thread.yield();
                }
            } catch (TransactionAbortedException e) {
                // Transaction was aborted mid-execution
            }
        }
        throw new RuntimeException("Transaction failed after " + maxRetries + " retries (livelock?)");
    }

    // ==================== BANK TRANSFER EXAMPLE ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Software Transactional Memory (STM) ===\n");

        int numAccounts = 10;
        @SuppressWarnings("unchecked")
        TVar<Long>[] accounts = new TVar[numAccounts];
        for (int i = 0; i < numAccounts; i++) {
            accounts[i] = new TVar<>(1000L);
        }

        int numThreads = 8;
        int transfersPerThread = 100_000;
        AtomicInteger successfulTransfers = new AtomicInteger(0);
        AtomicInteger failedAttempts = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < transfersPerThread; i++) {
                    int from = rng.nextInt(numAccounts);
                    int to = rng.nextInt(numAccounts);
                    if (from == to) continue;
                    long amount = rng.nextInt(10) + 1;

                    final int f = from, toIdx = to;
                    final long amt = amount;
                    atomic(tx -> {
                        long fromBal = tx.read(accounts[f]);
                        long toBal = tx.read(accounts[toIdx]);
                        if (fromBal >= amt) {
                            tx.write(accounts[f], fromBal - amt);
                            tx.write(accounts[toIdx], toBal + amt);
                        }
                        return null;
                    });
                    successfulTransfers.incrementAndGet();
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        // Verify conservation of money
        long totalMoney = 0;
        for (TVar<Long> account : accounts) {
            totalMoney += account.read();
        }

        System.out.println("Threads: " + numThreads + ", Transfers/thread: " + transfersPerThread);
        System.out.println("Successful transfers: " + successfulTransfers.get());
        System.out.println("Total money (should be " + (numAccounts * 1000L) + "): " + totalMoney);
        System.out.println("Conservation of money: " + (totalMoney == numAccounts * 1000L));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (successfulTransfers.get() * 1_000_000_000L / elapsed) + " tx/sec");
        System.out.println("\nKey insight: STM provides composable atomic operations.");
        System.out.println("No explicit lock ordering needed - STM handles it.");
        System.out.println("Used in Clojure (Refs), Haskell (STM monad), and database engines.");
    }
}
