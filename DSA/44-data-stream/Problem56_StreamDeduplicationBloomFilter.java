import java.util.*;
import java.util.function.*;

/**
 * Problem 56: Stream Deduplication with Bloom Filter
 * 
 * Production Relevance:
 * - At-least-once delivery requires dedup at consumer; exact sets don't scale for billions of IDs
 * - Bloom filters: O(1) lookup, fixed memory, tunable false positive rate
 * - Used in Kafka dedup, network packet dedup, web crawler URL dedup
 * - Rotating bloom filters handle time-windowed dedup without unbounded growth
 * 
 * Architect Considerations:
 * - False positives = dropped valid messages (acceptable if rare)
 * - False negatives = impossible (no duplicates slip through)
 * - Size formula: m = -n*ln(p) / (ln2)^2 where n=expected items, p=desired FP rate
 * - Rotating/counting bloom filters for expiration support
 */
public class Problem56_StreamDeduplicationBloomFilter {

    static class BloomFilter {
        private final BitSet bits;
        private final int size;
        private final int numHashes;
        private int insertedCount;

        BloomFilter(int expectedItems, double falsePositiveRate) {
            this.size = optimalSize(expectedItems, falsePositiveRate);
            this.numHashes = optimalHashes(size, expectedItems);
            this.bits = new BitSet(size);
        }

        private int optimalSize(int n, double p) {
            return (int) Math.ceil(-n * Math.log(p) / (Math.log(2) * Math.log(2)));
        }

        private int optimalHashes(int m, int n) {
            return Math.max(1, (int) Math.round((double) m / n * Math.log(2)));
        }

        private int[] getHashes(String key) {
            int[] hashes = new int[numHashes];
            int h1 = key.hashCode();
            int h2 = key.hashCode() * 31 + 17;
            for (int i = 0; i < numHashes; i++) {
                hashes[i] = Math.abs((h1 + i * h2) % size);
            }
            return hashes;
        }

        public void add(String key) {
            for (int hash : getHashes(key)) bits.set(hash);
            insertedCount++;
        }

        public boolean mightContain(String key) {
            for (int hash : getHashes(key)) {
                if (!bits.get(hash)) return false;
            }
            return true;
        }

        public int getInsertedCount() { return insertedCount; }
        public int getBitSize() { return size; }
        public int getNumHashes() { return numHashes; }
    }

    // Rotating bloom filter for time-windowed dedup
    static class RotatingBloomDedup {
        private BloomFilter current;
        private BloomFilter previous;
        private final int expectedPerWindow;
        private final double fpRate;
        private final int rotateAfter;

        RotatingBloomDedup(int expectedPerWindow, double fpRate) {
            this.expectedPerWindow = expectedPerWindow;
            this.fpRate = fpRate;
            this.rotateAfter = expectedPerWindow;
            this.current = new BloomFilter(expectedPerWindow, fpRate);
            this.previous = new BloomFilter(expectedPerWindow, fpRate);
        }

        public boolean isDuplicate(String id) {
            if (current.mightContain(id) || previous.mightContain(id)) return true;
            current.add(id);
            if (current.getInsertedCount() >= rotateAfter) rotate();
            return false;
        }

        private void rotate() {
            previous = current;
            current = new BloomFilter(expectedPerWindow, fpRate);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Stream Deduplication with Bloom Filter ===\n");

        RotatingBloomDedup dedup = new RotatingBloomDedup(10000, 0.01);

        // Simulate stream with duplicates
        String[] events = {"evt-1", "evt-2", "evt-3", "evt-1", "evt-2", "evt-4", "evt-5", "evt-3"};
        int dupsDetected = 0;
        for (String evt : events) {
            boolean dup = dedup.isDuplicate(evt);
            if (dup) dupsDetected++;
            System.out.printf("%-8s -> %s%n", evt, dup ? "DUPLICATE (dropped)" : "NEW (processed)");
        }
        System.out.printf("%nDuplicates detected: %d%n", dupsDetected);

        // Show bloom filter stats
        BloomFilter bf = new BloomFilter(1000000, 0.001);
        System.out.printf("%nBloom filter for 1M items @ 0.1%% FP: %d bits (%d KB), %d hashes%n",
                bf.getBitSize(), bf.getBitSize() / 8 / 1024, bf.getNumHashes());
    }
}
