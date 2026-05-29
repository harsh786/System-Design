import java.util.*;

/**
 * Problem 65: Stream Replay from Offset
 * 
 * Production Relevance:
 * - Kafka's killer feature: replay from any offset for reprocessing after bug fixes
 * - Enables "time travel" for data pipelines: recompute with new logic on historical data
 * - Used for backfilling derived stores, A/B testing pipeline changes, disaster recovery
 * - Consumer group offset management is critical for exactly-once replay
 * 
 * Architect Considerations:
 * - Retention policy determines replay window (e.g., 7 days, infinite with tiered storage)
 * - Replay must handle schema evolution if format changed between original and replay
 * - Dual-write during replay: serve live traffic while catching up
 * - Offset reset strategies: earliest, latest, timestamp-based, specific offset
 */
public class Problem65_StreamReplayFromOffset {

    static class Record {
        long offset;
        String key;
        String value;
        long timestamp;

        Record(long offset, String key, String value, long timestamp) {
            this.offset = offset; this.key = key; this.value = value; this.timestamp = timestamp;
        }

        @Override
        public String toString() {
            return String.format("[offset=%d, key=%s, val=%s, ts=%d]", offset, key, value, timestamp);
        }
    }

    // Simulates a Kafka partition log
    static class PartitionLog {
        private final List<Record> log = new ArrayList<>();
        private long nextOffset = 0;

        public long append(String key, String value, long timestamp) {
            long offset = nextOffset++;
            log.add(new Record(offset, key, value, timestamp));
            return offset;
        }

        public List<Record> readFrom(long startOffset, int maxRecords) {
            List<Record> result = new ArrayList<>();
            for (int i = (int) startOffset; i < log.size() && result.size() < maxRecords; i++) {
                result.add(log.get(i));
            }
            return result;
        }

        public long findOffsetByTimestamp(long timestamp) {
            // Binary search for first record with ts >= timestamp
            int lo = 0, hi = log.size() - 1;
            long result = log.size(); // default: end
            while (lo <= hi) {
                int mid = (lo + hi) / 2;
                if (log.get(mid).timestamp >= timestamp) {
                    result = mid;
                    hi = mid - 1;
                } else {
                    lo = mid + 1;
                }
            }
            return result;
        }

        public long getEarliestOffset() { return log.isEmpty() ? 0 : log.get(0).offset; }
        public long getLatestOffset() { return nextOffset; }
        public int size() { return log.size(); }
    }

    // Consumer with offset management
    static class ReplayableConsumer {
        private final String groupId;
        private long currentOffset;
        private final Map<String, String> processedState = new LinkedHashMap<>();
        private int recordsProcessed = 0;

        ReplayableConsumer(String groupId, long startOffset) {
            this.groupId = groupId;
            this.currentOffset = startOffset;
        }

        public void consume(PartitionLog log, int batchSize) {
            List<Record> batch = log.readFrom(currentOffset, batchSize);
            for (Record r : batch) {
                // Process: simple key-value materialization
                processedState.put(r.key, r.value);
                currentOffset = r.offset + 1;
                recordsProcessed++;
            }
        }

        public void seekToOffset(long offset) {
            this.currentOffset = offset;
            processedState.clear(); // Reset state for replay
            recordsProcessed = 0;
        }

        public void seekToTimestamp(PartitionLog log, long timestamp) {
            long offset = log.findOffsetByTimestamp(timestamp);
            seekToOffset(offset);
        }

        public long getCurrentOffset() { return currentOffset; }
        public int getRecordsProcessed() { return recordsProcessed; }
        public Map<String, String> getState() { return processedState; }
    }

    public static void main(String[] args) {
        System.out.println("=== Stream Replay from Offset ===\n");

        PartitionLog log = new PartitionLog();

        // Produce records
        log.append("user1", "signup", 1000);
        log.append("user2", "signup", 2000);
        log.append("user1", "purchase:$50", 3000);
        log.append("user3", "signup", 4000);
        log.append("user2", "purchase:$100", 5000);
        log.append("user1", "purchase:$75", 6000);
        log.append("user3", "purchase:$200", 7000);

        System.out.printf("Log: %d records, offsets [%d, %d)%n%n",
                log.size(), log.getEarliestOffset(), log.getLatestOffset());

        // Consumer processes all records
        ReplayableConsumer consumer = new ReplayableConsumer("analytics-v1", 0);
        consumer.consume(log, 100);
        System.out.println("Initial processing complete:");
        System.out.println("  State: " + consumer.getState());
        System.out.println("  Offset: " + consumer.getCurrentOffset());

        // Bug found! Need to replay from offset 2 with fixed logic
        System.out.println("\n--- Replaying from offset 2 (after bug fix) ---");
        consumer.seekToOffset(2);
        consumer.consume(log, 100);
        System.out.println("  State after replay: " + consumer.getState());
        System.out.println("  Records reprocessed: " + consumer.getRecordsProcessed());

        // Replay from timestamp
        System.out.println("\n--- Replay from timestamp 4000 ---");
        consumer.seekToTimestamp(log, 4000);
        System.out.println("  Seeked to offset: " + consumer.getCurrentOffset());
        consumer.consume(log, 100);
        System.out.println("  State: " + consumer.getState());
    }
}
