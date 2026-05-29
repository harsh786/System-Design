import java.util.*;
import java.nio.charset.*;

/**
 * Problem 60: Bloom Filter with False Positive Rate Control
 * 
 * PRODUCTION MAPPING: Cassandra (SSTable lookup), HBase, Chrome (malicious URL check),
 *                     Medium (article recommendation dedup), Akamai CDN
 * 
 * Key Properties:
 * - Probabilistic: no false negatives, controlled false positive rate
 * - Space efficient: ~10 bits/element for 1% FPR
 * - O(k) insert and lookup where k = number of hash functions
 * 
 * Formulas:
 * - Optimal bit array size: m = -n*ln(p) / (ln2)^2
 * - Optimal hash count: k = (m/n) * ln2
 * Where n = expected insertions, p = desired false positive rate
 * 
 * Trade-offs:
 * - Cannot delete (use Counting Bloom Filter for that)
 * - FPR increases as filter fills up
 * - Need to size upfront (or use Scalable Bloom Filter)
 */
public class Problem60_BloomFilter {

    static class BloomFilter {
        private final BitSet bitSet;
        private final int bitSize;
        private final int hashCount;
        private int insertedCount = 0;

        /**
         * Create Bloom filter with desired false positive rate.
         * @param expectedInsertions number of elements expected
         * @param falsePositiveRate desired FPR (e.g., 0.01 for 1%)
         */
        public BloomFilter(int expectedInsertions, double falsePositiveRate) {
            this.bitSize = optimalBitSize(expectedInsertions, falsePositiveRate);
            this.hashCount = optimalHashCount(expectedInsertions, bitSize);
            this.bitSet = new BitSet(bitSize);
        }

        public BloomFilter(int bitSize, int hashCount) {
            this.bitSize = bitSize;
            this.hashCount = hashCount;
            this.bitSet = new BitSet(bitSize);
        }

        public void add(String element) {
            for (int i = 0; i < hashCount; i++) {
                int index = getHash(element, i);
                bitSet.set(index);
            }
            insertedCount++;
        }

        /**
         * Returns true if element MIGHT be in set (possible false positive).
         * Returns false if element is DEFINITELY NOT in set.
         */
        public boolean mightContain(String element) {
            for (int i = 0; i < hashCount; i++) {
                int index = getHash(element, i);
                if (!bitSet.get(index)) return false;
            }
            return true;
        }

        /**
         * Estimate current false positive probability based on fill ratio.
         * Formula: (1 - e^(-kn/m))^k
         */
        public double estimatedFPR() {
            double fillRatio = (double) bitSet.cardinality() / bitSize;
            return Math.pow(fillRatio, hashCount);
        }

        /**
         * Double hashing technique (Kirsch-Mitzenmacher optimization):
         * h_i(x) = h1(x) + i * h2(x) mod m
         * Only need 2 independent hash functions to simulate k hash functions.
         */
        private int getHash(String element, int i) {
            byte[] bytes = element.getBytes(StandardCharsets.UTF_8);
            int h1 = murmurHash(bytes, 0);
            int h2 = murmurHash(bytes, h1);
            int combined = h1 + i * h2;
            // Ensure positive
            return Math.abs(combined % bitSize);
        }

        /** Simple murmur-inspired hash */
        private int murmurHash(byte[] data, int seed) {
            int h = seed;
            for (byte b : data) {
                h ^= b;
                h *= 0x5bd1e995;
                h ^= h >>> 15;
            }
            return h;
        }

        static int optimalBitSize(int n, double p) {
            return (int) Math.ceil(-n * Math.log(p) / (Math.log(2) * Math.log(2)));
        }

        static int optimalHashCount(int n, int m) {
            return Math.max(1, (int) Math.round((double) m / n * Math.log(2)));
        }

        public int getBitSize() { return bitSize; }
        public int getHashCount() { return hashCount; }
        public int getInsertedCount() { return insertedCount; }
        public double fillRatio() { return (double) bitSet.cardinality() / bitSize; }
    }

    public static void main(String[] args) {
        System.out.println("=== Bloom Filter with FPR Control ===\n");

        // Test 1: No false negatives
        BloomFilter bf = new BloomFilter(1000, 0.01);
        System.out.printf("Config: %d bits, %d hashes (for 1000 elements, 1%% FPR)\n",
            bf.getBitSize(), bf.getHashCount());

        for (int i = 0; i < 1000; i++) {
            bf.add("element-" + i);
        }
        for (int i = 0; i < 1000; i++) {
            assert bf.mightContain("element-" + i) : "False negative at " + i;
        }
        System.out.println("PASS: Zero false negatives for 1000 inserted elements");

        // Test 2: Measure actual false positive rate
        int falsePositives = 0;
        int testCount = 10000;
        for (int i = 0; i < testCount; i++) {
            if (bf.mightContain("not-in-set-" + i)) {
                falsePositives++;
            }
        }
        double actualFPR = (double) falsePositives / testCount;
        System.out.printf("PASS: Actual FPR = %.4f (target = 0.01)\n", actualFPR);
        assert actualFPR < 0.02 : "FPR too high: " + actualFPR;

        // Test 3: Different FPR targets
        System.out.println("\n--- FPR vs Size trade-off ---");
        for (double targetFPR : new double[]{0.1, 0.01, 0.001, 0.0001}) {
            BloomFilter f = new BloomFilter(10000, targetFPR);
            System.out.printf("  Target FPR=%.4f -> %d bits (%d bits/element), %d hashes\n",
                targetFPR, f.getBitSize(), f.getBitSize()/10000, f.getHashCount());
        }

        // Test 4: Fill ratio impact on FPR
        System.out.println("\n--- Fill ratio vs actual FPR ---");
        bf = new BloomFilter(10000, 0.01);
        for (int inserted : new int[]{1000, 5000, 10000, 15000, 20000}) {
            BloomFilter test = new BloomFilter(10000, 0.01);
            for (int i = 0; i < inserted; i++) test.add("item-" + i);
            
            int fp = 0;
            for (int i = 0; i < 10000; i++) {
                if (test.mightContain("miss-" + i)) fp++;
            }
            System.out.printf("  Inserted=%5d, fill=%.2f, FPR=%.4f\n",
                inserted, test.fillRatio(), (double)fp/10000);
        }

        // Test 5: Definitely not in set
        bf = new BloomFilter(100, 0.01);
        bf.add("hello");
        bf.add("world");
        assert !bf.mightContain("xyz123abc") : "Should definitely not contain random string";
        System.out.println("\nPASS: Correctly identifies elements not in set");

        // Test 6: Space comparison with HashSet
        int n = 100000;
        BloomFilter compact = new BloomFilter(n, 0.01);
        int bloomBytes = compact.getBitSize() / 8;
        int hashSetEstimate = n * 50; // rough estimate for HashSet<String>
        System.out.printf("\nSpace for %d elements: Bloom=%d KB, HashSet~%d KB (%.1fx savings)\n",
            n, bloomBytes/1024, hashSetEstimate/1024, (double)hashSetEstimate/bloomBytes);

        System.out.println("\nAll tests passed!");
    }
}
