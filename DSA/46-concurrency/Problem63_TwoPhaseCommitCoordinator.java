import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;

/**
 * Problem 63: Two-Phase Commit (2PC) Coordinator
 * 
 * REAL-WORLD USAGE:
 * - Distributed databases (MySQL XA transactions, PostgreSQL 2PC)
 * - Microservices saga coordination (Narayana, Atomikos)
 * - Message queues with exactly-once delivery (Kafka transactions)
 * - Distributed file systems (HDFS namenode coordination)
 * 
 * THE PROTOCOL:
 * Phase 1 (PREPARE/VOTE):
 *   Coordinator → all Participants: "Can you commit?"
 *   Participants: write to WAL, lock resources, reply YES/NO
 * 
 * Phase 2 (COMMIT/ABORT):
 *   If ALL voted YES → Coordinator: "COMMIT" → Participants commit
 *   If ANY voted NO  → Coordinator: "ABORT"  → Participants rollback
 * 
 * GUARANTEES:
 * - Atomic: either all commit or all abort
 * - Consistent: no partial commits visible
 * 
 * PITFALLS (why 2PC is avoided in modern systems):
 * 1. BLOCKING: if coordinator crashes after PREPARE, participants are stuck
 *    holding locks indefinitely (the "blocking problem")
 * 2. Single point of failure: coordinator crash = system halt
 * 3. Latency: 2 round-trips minimum (prepare + commit)
 * 4. Network partitions: participant may not receive commit/abort decision
 * 5. In practice, use SAGA pattern or 3PC (non-blocking) instead
 * 
 * MEMORY ORDERING / CONCURRENCY:
 * - WAL writes must be durable BEFORE voting YES (fsync)
 * - Decision must be logged BEFORE sending commit/abort messages
 * - Participants must apply changes BEFORE acknowledging commit
 */
public class Problem63_TwoPhaseCommitCoordinator {

    enum TransactionState { INIT, PREPARING, PREPARED, COMMITTING, COMMITTED, ABORTING, ABORTED }
    enum Vote { YES, NO, TIMEOUT }

    // ==================== PARTICIPANT ====================
    static class Participant {
        private final String id;
        private final ConcurrentHashMap<String, String> dataStore = new ConcurrentHashMap<>();
        private final ConcurrentHashMap<Long, Map<String, String>> preparedWrites = new ConcurrentHashMap<>();
        private final double failureProbability;
        private final Random rng = new Random();
        private volatile boolean crashed = false;

        Participant(String id, double failureProbability) {
            this.id = id;
            this.failureProbability = failureProbability;
        }

        /**
         * Phase 1: Prepare. Validate and lock resources.
         * Returns YES if can commit, NO otherwise.
         */
        public Vote prepare(long txId, Map<String, String> writes) {
            if (crashed) return Vote.TIMEOUT;
            // Simulate random failure
            if (rng.nextDouble() < failureProbability) {
                return Vote.NO; // Resource unavailable, constraint violation, etc.
            }
            // "Write to WAL" (in reality: fsync to disk before responding)
            preparedWrites.put(txId, new HashMap<>(writes));
            // Resources are now "locked" for this transaction
            return Vote.YES;
        }

        /** Phase 2: Commit. Apply the prepared writes. */
        public boolean commit(long txId) {
            if (crashed) return false;
            Map<String, String> writes = preparedWrites.remove(txId);
            if (writes == null) return false;
            dataStore.putAll(writes);
            return true;
        }

        /** Phase 2: Abort. Release locks, discard prepared writes. */
        public boolean abort(long txId) {
            preparedWrites.remove(txId);
            return true;
        }

        public String get(String key) { return dataStore.get(key); }
        public void crash() { crashed = true; }
        public void recover() { crashed = false; }
        public String getId() { return id; }
    }

    // ==================== COORDINATOR ====================
    static class Coordinator {
        private final List<Participant> participants;
        private final AtomicLong txIdCounter = new AtomicLong(0);
        private final ConcurrentHashMap<Long, TransactionState> txLog = new ConcurrentHashMap<>();
        private final AtomicInteger committed = new AtomicInteger(0);
        private final AtomicInteger aborted = new AtomicInteger(0);
        private final long timeoutMs;

        Coordinator(List<Participant> participants, long timeoutMs) {
            this.participants = participants;
            this.timeoutMs = timeoutMs;
        }

        /**
         * Execute a distributed transaction across all participants.
         * Returns true if committed, false if aborted.
         */
        public boolean executeTransaction(Map<String, String> writes) {
            long txId = txIdCounter.incrementAndGet();
            txLog.put(txId, TransactionState.PREPARING);

            // ===== PHASE 1: PREPARE =====
            List<Vote> votes = new ArrayList<>();
            ExecutorService executor = Executors.newFixedThreadPool(participants.size());
            List<Future<Vote>> futures = new ArrayList<>();

            for (Participant p : participants) {
                futures.add(executor.submit(() -> p.prepare(txId, writes)));
            }

            for (Future<Vote> f : futures) {
                try {
                    Vote vote = f.get(timeoutMs, TimeUnit.MILLISECONDS);
                    votes.add(vote);
                } catch (Exception e) {
                    votes.add(Vote.TIMEOUT);
                }
            }
            executor.shutdown();

            // ===== DECISION =====
            boolean allYes = votes.stream().allMatch(v -> v == Vote.YES);

            // LOG decision BEFORE sending phase 2 messages (crash recovery point)
            txLog.put(txId, allYes ? TransactionState.COMMITTING : TransactionState.ABORTING);

            // ===== PHASE 2: COMMIT or ABORT =====
            if (allYes) {
                for (Participant p : participants) {
                    p.commit(txId); // In reality: retry until acknowledged
                }
                txLog.put(txId, TransactionState.COMMITTED);
                committed.incrementAndGet();
                return true;
            } else {
                for (Participant p : participants) {
                    p.abort(txId);
                }
                txLog.put(txId, TransactionState.ABORTED);
                aborted.incrementAndGet();
                return false;
            }
        }

        public int getCommitted() { return committed.get(); }
        public int getAborted() { return aborted.get(); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Two-Phase Commit (2PC) Coordinator ===\n");

        // Setup: 3 participants with varying failure rates
        List<Participant> participants = List.of(
                new Participant("DB-Primary", 0.01),
                new Participant("DB-Replica", 0.02),
                new Participant("Cache-Node", 0.05)
        );

        Coordinator coordinator = new Coordinator(participants, 100);

        int numThreads = 4;
        int txPerThread = 10_000;
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            final int tid = t;
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < txPerThread; i++) {
                    Map<String, String> writes = Map.of(
                            "key-" + tid + "-" + i, "value-" + i
                    );
                    coordinator.executeTransaction(writes);
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        int totalTx = numThreads * txPerThread;
        System.out.println("Participants: " + participants.size());
        System.out.println("Total transactions: " + totalTx);
        System.out.println("Committed: " + coordinator.getCommitted());
        System.out.println("Aborted: " + coordinator.getAborted());
        System.out.println("Abort rate: " + (coordinator.getAborted() * 100 / totalTx) + "%");
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (totalTx * 1_000_000_000L / elapsed) + " tx/sec");
        System.out.println("\nKey insight: 2PC guarantees atomicity but is BLOCKING.");
        System.out.println("Modern systems prefer SAGA (compensating transactions) for availability.");
    }
}
