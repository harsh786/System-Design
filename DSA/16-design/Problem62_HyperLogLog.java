import java.util.*;
import java.nio.charset.*;

/**
 * Problem 62: HyperLogLog for Cardinality Estimation
 * 
 * PRODUCTION MAPPING: Redis PFCOUNT/PFADD, BigQuery approximate COUNT DISTINCT,
 *                     Presto/Trino, Flink, network monitoring (unique IPs)
 * 
 * Key Insight: Uses the observation that in a random binary string, the probability
 * of seeing k leading zeros is 1/2^k. So max leading zeros ~ log2(cardinality).
 * 
 * Algorithm:
 * 1. Hash element to uniform bit string
 * 2. Use first p bits as bucket index (2^p buckets)
 * 3. Count leading zeros in remaining bits
 * 4. Store max leading zeros per bucket
 * 5. Estimate: harmonic mean across buckets with bias correction
 * 
 * Properties:
 * - O(m) space where m = 2^p buckets (typically 1-2 KB for ~2% error)
 * - Standard error: 1.04 / sqrt(m)
 * - Mergeable: can union multiple HLLs (useful for distributed counting)
 * 
 * Trade-offs:
 * - Very low memory (~12 KB for 0.81% error with 16384 buckets)
 * - Cannot remove elements
 * - Less accurate for small cardinalities (use LinearCounting correction)
 */
public class Problem62_HyperLogLog {

    static class HyperLogLog {
        private final int p;           // precision (number of bits for bucket index)
        private final int m;           // number of buckets = 2^p
        private final int[] buckets;   // max leading zeros per bucket
        private final double alphaMM;  // bias correction constant * m * m

        public HyperLogLog(int precision) {
            this.p = precision;
            this.m = 1 << p;
            this.buckets = new int[m];
            
            // Alpha correction factor
            double alpha;
            switch (m) {
                case 16: alpha = 0.673; break;
                case 32: alpha = 0.697; break;
                case 64: alpha = 0.709; break;
                default: alpha = 0.7213 / (1 + 1.079 / m);
            }
            this.alphaMM = alpha * m * m;
        }

        public void add(String element) {
            long hash = hash64(element);
            // First p bits determine bucket
            int bucketIndex = (int)(hash >>> (64 - p));
            // Remaining bits: count leading zeros + 1
            long remaining = (hash << p) | (1L << (p - 1)); // ensure at least 1 bit set
            int leadingZeros = Long.numberOfLeadingZeros(remaining) + 1;
            buckets[bucketIndex] = Math.max(buckets[bucketIndex], leadingZeros);
        }

        public long estimate() {
            // Harmonic mean of 2^bucket[i]
            double sum = 0;
            int zerosCount = 0;
            for (int bucket : buckets) {
                sum += 1.0 / (1L << bucket);
                if (bucket == 0) zerosCount++;
            }
            double estimate = alphaMM / sum;

            // Small range correction (LinearCounting)
            if (estimate <= 2.5 * m && zerosCount > 0) {
                estimate = m * Math.log((double) m / zerosCount);
            }
            // Large range correction (for 32-bit hash, not needed for 64-bit)

            return Math.round(estimate);
        }

        /**
         * Merge another HLL into this one (union operation).
         * Used in distributed systems to combine counts from multiple nodes.
         */
        public void merge(HyperLogLog other) {
            if (this.p != other.p) throw new IllegalArgumentException("Precision mismatch");
            for (int i = 0; i < m; i++) {
                buckets[i] = Math.max(buckets[i], other.buckets[i]);
            }
        }

        public double standardError() {
            return 1.04 / Math.sqrt(m);
        }

        private long hash64(String element) {
            // MurmurHash3-inspired 64-bit hash
            byte[] data = element.getBytes(StandardCharsets.UTF_8);
            long h = 0xcbf29ce484222325L;
            for (byte b : data) {
                h ^= b;
                h *= 0x100000001b3L;
            }
            h ^= h >>> 33;
            h *= 0xff51afd7ed558ccdL;
            h ^= h >>> 33;
            return h;
        }

        public int getMemoryBytes() { return m; } // 1 byte per bucket (can optimize to 6 bits)
    }

    public static void main(String[] args) {
        System.out.println("=== HyperLogLog Cardinality Estimation ===\n");

        // Test 1: Basic cardinality estimation
        HyperLogLog hll = new HyperLogLog(14); // 16384 buckets, ~0.81% error
        int actualCardinality = 100000;
        for (int i = 0; i < actualCardinality; i++) {
            hll.add("user-" + i);
        }
        long estimate = hll.estimate();
        double errorPct = Math.abs(estimate - actualCardinality) * 100.0 / actualCardinality;
        System.out.printf("Actual: %d, Estimated: %d, Error: %.2f%%\n", 
            actualCardinality, estimate, errorPct);
        System.out.printf("Theoretical std error: %.2f%%\n", hll.standardError() * 100);
        assert errorPct < 5 : "Error too high: " + errorPct;
        System.out.println("PASS: Estimation within acceptable error");

        // Test 2: Duplicate insensitivity (idempotent)
        hll = new HyperLogLog(14);
        for (int i = 0; i < 1000; i++) {
            hll.add("same-element"); // same element 1000 times
        }
        estimate = hll.estimate();
        assert estimate <= 2 : "Duplicates should count as 1, got: " + estimate;
        System.out.println("PASS: Duplicates don't inflate count (est=" + estimate + ")");

        // Test 3: Merge (distributed counting)
        HyperLogLog hll1 = new HyperLogLog(12);
        HyperLogLog hll2 = new HyperLogLog(12);
        // Node 1 sees users 0-4999, Node 2 sees users 2500-7499 (overlap!)
        for (int i = 0; i < 5000; i++) hll1.add("user-" + i);
        for (int i = 2500; i < 7500; i++) hll2.add("user-" + i);
        
        hll1.merge(hll2);
        estimate = hll1.estimate();
        errorPct = Math.abs(estimate - 7500) * 100.0 / 7500;
        System.out.printf("Merged: actual=7500, estimated=%d, error=%.2f%%\n", estimate, errorPct);
        assert errorPct < 5;
        System.out.println("PASS: Merge correctly handles overlap");

        // Test 4: Memory efficiency
        System.out.println("\n--- Memory vs Precision ---");
        for (int precision : new int[]{8, 10, 12, 14, 16}) {
            HyperLogLog h = new HyperLogLog(precision);
            for (int i = 0; i < 1000000; i++) h.add("elem-" + i);
            long est = h.estimate();
            double err = Math.abs(est - 1000000) * 100.0 / 1000000;
            System.out.printf("  p=%2d, buckets=%6d, memory=%6d bytes, error=%.2f%%\n",
                precision, 1 << precision, h.getMemoryBytes(), err);
        }

        // Test 5: Comparison with exact HashSet
        int n = 1000000;
        int hllMemory = 1 << 14; // ~16KB
        int hashSetMemory = n * 50; // ~50MB for String HashSet
        System.out.printf("\nFor %d unique elements:\n", n);
        System.out.printf("  HLL:     %d KB (%.2f%% error)\n", hllMemory / 1024, 0.81);
        System.out.printf("  HashSet: %d KB (exact)\n", hashSetMemory / 1024);
        System.out.printf("  Savings: %.0fx\n", (double) hashSetMemory / hllMemory);

        // Test 6: Various cardinalities
        System.out.println("\n--- Accuracy across cardinalities ---");
        for (int card : new int[]{100, 1000, 10000, 100000, 1000000}) {
            HyperLogLog h = new HyperLogLog(14);
            for (int i = 0; i < card; i++) h.add("x-" + i);
            long est2 = h.estimate();
            double err2 = Math.abs(est2 - card) * 100.0 / card;
            System.out.printf("  n=%7d, estimate=%7d, error=%.2f%%\n", card, est2, err2);
        }

        System.out.println("\nAll tests passed!");
    }
}
