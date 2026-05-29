import java.util.*;
import java.util.function.*;

/**
 * Problem 64: Stream Repartitioning
 * 
 * Production Relevance:
 * - Repartitioning (re-keying) needed when downstream processing requires different grouping
 * - E.g., events keyed by userId need re-keying by sessionId for session analytics
 * - Kafka: repartition = produce to new topic with new key (shuffle)
 * - Expensive: full network shuffle, new topic, doubles storage temporarily
 * 
 * Architect Considerations:
 * - Repartitioning breaks per-partition ordering guarantees
 * - Must handle hot keys (skew) that overload target partitions
 * - Co-partitioning: two streams must share same key+partition count for joins
 * - Partition count changes require consumer rebalance
 */
public class Problem64_StreamRepartitioning {

    static class Record {
        String key;
        String value;
        int sourcePartition;

        Record(String key, String value, int sourcePartition) {
            this.key = key; this.value = value; this.sourcePartition = sourcePartition;
        }
    }

    static class Partitioner {
        private final int numPartitions;

        Partitioner(int numPartitions) { this.numPartitions = numPartitions; }

        public int partition(String key) {
            return Math.abs(key.hashCode()) % numPartitions;
        }

        // Custom partitioner for hot key spreading
        public int partitionWithSalting(String key, boolean isHotKey) {
            if (isHotKey) {
                // Spread hot key across multiple partitions with salt
                int salt = (int) (Math.random() * numPartitions);
                return salt % numPartitions;
            }
            return partition(key);
        }
    }

    static class RepartitionOperator {
        private final int sourcePartitions;
        private final int targetPartitions;
        private final Function<Record, String> newKeyExtractor;
        private final Partitioner targetPartitioner;
        // Target partitions state
        private final List<List<Record>> targetBuffers;
        private int totalRepartitioned = 0;

        RepartitionOperator(int sourcePartitions, int targetPartitions, Function<Record, String> keyExtractor) {
            this.sourcePartitions = sourcePartitions;
            this.targetPartitions = targetPartitions;
            this.newKeyExtractor = keyExtractor;
            this.targetPartitioner = new Partitioner(targetPartitions);
            this.targetBuffers = new ArrayList<>();
            for (int i = 0; i < targetPartitions; i++) targetBuffers.add(new ArrayList<>());
        }

        public void repartition(Record record) {
            String newKey = newKeyExtractor.apply(record);
            int targetPartition = targetPartitioner.partition(newKey);
            Record rekeyed = new Record(newKey, record.value, targetPartition);
            targetBuffers.get(targetPartition).add(rekeyed);
            totalRepartitioned++;
        }

        public Map<Integer, Integer> getPartitionDistribution() {
            Map<Integer, Integer> dist = new TreeMap<>();
            for (int i = 0; i < targetPartitions; i++) {
                dist.put(i, targetBuffers.get(i).size());
            }
            return dist;
        }

        public double getSkewFactor() {
            int max = targetBuffers.stream().mapToInt(List::size).max().orElse(0);
            double avg = (double) totalRepartitioned / targetPartitions;
            return avg == 0 ? 0 : max / avg;
        }

        public int getTotalRepartitioned() { return totalRepartitioned; }
    }

    public static void main(String[] args) {
        System.out.println("=== Stream Repartitioning ===\n");

        // Scenario: events keyed by userId, repartition by region (extracted from value)
        RepartitionOperator repart = new RepartitionOperator(4, 6,
            record -> record.value.split(":")[0] // Extract region from value
        );

        // Simulate events
        String[][] events = {
            {"user1", "US:click"}, {"user2", "EU:view"}, {"user3", "US:purchase"},
            {"user4", "APAC:click"}, {"user5", "EU:purchase"}, {"user6", "US:view"},
            {"user7", "US:click"}, {"user8", "EU:click"}, {"user9", "APAC:view"},
            {"user10", "US:purchase"}, {"user11", "US:click"}, {"user12", "EU:view"},
        };

        for (int i = 0; i < events.length; i++) {
            Record r = new Record(events[i][0], events[i][1], i % 4);
            repart.repartition(r);
        }

        System.out.println("Source: 4 partitions keyed by userId");
        System.out.println("Target: 6 partitions keyed by region\n");
        System.out.println("Target partition distribution: " + repart.getPartitionDistribution());
        System.out.printf("Skew factor: %.2f (1.0 = perfect, higher = skewed)%n", repart.getSkewFactor());
        System.out.println("Total repartitioned: " + repart.getTotalRepartitioned());
    }
}
