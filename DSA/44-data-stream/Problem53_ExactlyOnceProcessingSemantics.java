import java.util.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 53: Exactly-Once Processing Semantics
 * 
 * Production Relevance:
 * - Critical for financial transactions, inventory updates, billing systems
 * - Kafka achieves this via idempotent producers + transactional consumers
 * - Flink uses distributed snapshots (Chandy-Lamport) for exactly-once
 * - Without it, duplicate processing causes revenue loss or data corruption
 * 
 * Architect Considerations:
 * - True exactly-once is impossible in general (FLP); we implement effectively-once
 * - Idempotency keys + deduplication + atomic commit of offset+state
 * - Performance cost: 2PC or epoch-based fencing adds latency
 * - Must handle zombie instances (fenced by epoch)
 */
public class Problem53_ExactlyOnceProcessingSemantics {

    static class Message {
        String id; // Idempotency key
        String payload;
        int partition;
        long offset;

        Message(String id, String payload, int partition, long offset) {
            this.id = id;
            this.payload = payload;
            this.partition = partition;
            this.offset = offset;
        }
    }

    static class TransactionalProcessor {
        // Committed offsets (atomically updated with state)
        private final Map<Integer, Long> committedOffsets = new HashMap<>();
        // Processing state
        private final Map<String, Integer> wordCounts = new HashMap<>();
        // Deduplication log (idempotency keys seen)
        private final Set<String> processedIds = new LinkedHashSet<>();
        private static final int DEDUP_WINDOW = 10000;
        // Epoch for fencing zombies
        private final AtomicLong epoch = new AtomicLong(0);
        private long activeEpoch;

        // Transactional begin
        public long beginTransaction() {
            activeEpoch = epoch.incrementAndGet();
            return activeEpoch;
        }

        // Process with dedup check
        public boolean process(Message msg, long txnEpoch) {
            // Fence check: reject if from old epoch (zombie)
            if (txnEpoch != activeEpoch) {
                System.out.println("  FENCED: zombie epoch " + txnEpoch + " vs active " + activeEpoch);
                return false;
            }
            // Dedup check
            if (processedIds.contains(msg.id)) {
                System.out.println("  DEDUP: skipping already-processed " + msg.id);
                return false;
            }
            // Offset check: skip if already committed past this
            Long committed = committedOffsets.get(msg.partition);
            if (committed != null && msg.offset <= committed) {
                System.out.println("  SKIP: offset " + msg.offset + " <= committed " + committed);
                return false;
            }
            // Process
            for (String word : msg.payload.split("\\s+")) {
                wordCounts.merge(word, 1, Integer::sum);
            }
            return true;
        }

        // Atomic commit: state + offset + dedup log together
        public void commitTransaction(Message msg, long txnEpoch) {
            if (txnEpoch != activeEpoch) return;
            committedOffsets.put(msg.partition, msg.offset);
            processedIds.add(msg.id);
            // Trim dedup window
            if (processedIds.size() > DEDUP_WINDOW) {
                Iterator<String> it = processedIds.iterator();
                it.next();
                it.remove();
            }
        }

        public Map<String, Integer> getState() {
            return Collections.unmodifiableMap(wordCounts);
        }

        public Map<Integer, Long> getCommittedOffsets() {
            return Collections.unmodifiableMap(committedOffsets);
        }
    }

    public static void main(String[] args) {
        TransactionalProcessor processor = new TransactionalProcessor();
        System.out.println("=== Exactly-Once Processing Semantics ===\n");

        // Normal processing
        Message m1 = new Message("msg-001", "hello world", 0, 1);
        long txn1 = processor.beginTransaction();
        boolean processed = processor.process(m1, txn1);
        System.out.println("Process msg-001: " + processed);
        processor.commitTransaction(m1, txn1);

        // Duplicate delivery (network retry)
        Message m1Dup = new Message("msg-001", "hello world", 0, 1);
        long txn2 = processor.beginTransaction();
        processed = processor.process(m1Dup, txn2);
        System.out.println("Process msg-001 (duplicate): " + processed);

        // Normal next message
        Message m2 = new Message("msg-002", "world hello foo", 0, 2);
        long txn3 = processor.beginTransaction();
        processed = processor.process(m2, txn3);
        System.out.println("Process msg-002: " + processed);
        processor.commitTransaction(m2, txn3);

        // Zombie scenario: old epoch tries to process
        Message m3 = new Message("msg-003", "bar baz", 0, 3);
        long txn4 = processor.beginTransaction();
        // Simulate zombie using stale epoch
        processed = processor.process(m3, txn3); // Using old epoch
        System.out.println("Zombie process msg-003 with old epoch: " + processed);

        System.out.println("\nFinal state: " + processor.getState());
        System.out.println("Committed offsets: " + processor.getCommittedOffsets());
    }
}
