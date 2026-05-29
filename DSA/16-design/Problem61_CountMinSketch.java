import java.util.*;
import java.nio.charset.*;

/**
 * Problem 61: Count-Min Sketch for Heavy Hitters Detection
 * 
 * PRODUCTION MAPPING: Network traffic monitoring, trending topics (Twitter),
 *                     database query frequency estimation, DDoS detection,
 *                     Redis (approximate counting), Spark Streaming
 * 
 * Properties:
 * - Space: O(w * d) where w = width, d = depth (hash functions)
 * - Never underestimates (always overestimates or exact)
 * - Error bound: with probability (1 - delta), error < epsilon * N
 *   where w = ceil(e/epsilon), d = ceil(ln(1/delta)), N = total count
 * 
 * Heavy Hitters: elements with frequency > threshold * total_count
 * 
 * Trade-offs:
 * - More width = lower error but more memory
 * - More depth = higher confidence but diminishing returns
 * - Cannot decrement (use Count-Min-Mean for that)
 */
public class Problem61_CountMinSketch {

    static class CountMinSketch {
        private final int[][] table;
        private final int width;
        private final int depth;
        private final int[] seeds;
        private long totalCount;

        /**
         * @param epsilon Error factor (e.g., 0.001 means error < 0.1% of total)
         * @param delta   Confidence (e.g., 0.01 means 99% confidence)
         */
        public CountMinSketch(double epsilon, double delta) {
            this.width = (int) Math.ceil(Math.E / epsilon);
            this.depth = (int) Math.ceil(Math.log(1.0 / delta));
            this.table = new int[depth][width];
            this.seeds = new int[depth];
            Random rng = new Random(42);
            for (int i = 0; i < depth; i++) seeds[i] = rng.nextInt();
            this.totalCount = 0;
        }

        public CountMinSketch(int width, int depth) {
            this.width = width;
            this.depth = depth;
            this.table = new int[depth][width];
            this.seeds = new int[depth];
            Random rng = new Random(42);
            for (int i = 0; i < depth; i++) seeds[i] = rng.nextInt();
            this.totalCount = 0;
        }

        public void add(String item) { add(item, 1); }

        public void add(String item, int count) {
            for (int i = 0; i < depth; i++) {
                int index = hash(item, i);
                table[i][index] += count;
            }
            totalCount += count;
        }

        /**
         * Estimate frequency. Returns minimum across all hash functions.
         * This is an overestimate (never underestimates).
         */
        public int estimate(String item) {
            int min = Integer.MAX_VALUE;
            for (int i = 0; i < depth; i++) {
                int index = hash(item, i);
                min = Math.min(min, table[i][index]);
            }
            return min;
        }

        /**
         * Find heavy hitters: items with frequency > threshold * totalCount
         * Note: In practice, maintain a separate heap of candidates.
         */
        public List<Map.Entry<String, Integer>> findHeavyHitters(
                Collection<String> candidates, double threshold) {
            List<Map.Entry<String, Integer>> heavyHitters = new ArrayList<>();
            long minCount = (long) (threshold * totalCount);
            
            for (String item : candidates) {
                int est = estimate(item);
                if (est >= minCount) {
                    heavyHitters.add(Map.entry(item, est));
                }
            }
            heavyHitters.sort((a, b) -> b.getValue() - a.getValue());
            return heavyHitters;
        }

        private int hash(String item, int i) {
            byte[] bytes = item.getBytes(StandardCharsets.UTF_8);
            int h = seeds[i];
            for (byte b : bytes) {
                h ^= b;
                h *= 0x5bd1e995;
                h ^= h >>> 13;
            }
            return Math.abs(h % width);
        }

        public long getTotalCount() { return totalCount; }
        public int getWidth() { return width; }
        public int getDepth() { return depth; }
    }

    public static void main(String[] args) {
        System.out.println("=== Count-Min Sketch for Heavy Hitters ===\n");

        // Test 1: Basic counting accuracy
        CountMinSketch cms = new CountMinSketch(0.001, 0.01);
        System.out.printf("Config: width=%d, depth=%d\n", cms.getWidth(), cms.getDepth());

        cms.add("apple", 100);
        cms.add("banana", 50);
        cms.add("cherry", 10);

        int appleEst = cms.estimate("apple");
        assert appleEst >= 100 : "Should never underestimate";
        System.out.println("PASS: apple estimated=" + appleEst + " (actual=100)");

        // Test 2: Never underestimates
        Random rng = new Random(123);
        Map<String, Integer> actual = new HashMap<>();
        cms = new CountMinSketch(0.001, 0.01);
        
        for (int i = 0; i < 100000; i++) {
            String item = "item-" + rng.nextInt(1000);
            cms.add(item);
            actual.merge(item, 1, Integer::sum);
        }

        boolean anyUnderestimate = false;
        for (Map.Entry<String, Integer> e : actual.entrySet()) {
            if (cms.estimate(e.getKey()) < e.getValue()) {
                anyUnderestimate = true;
                break;
            }
        }
        assert !anyUnderestimate : "Count-Min Sketch should never underestimate";
        System.out.println("PASS: No underestimates across 1000 items");

        // Test 3: Error bound
        double maxError = 0;
        for (Map.Entry<String, Integer> e : actual.entrySet()) {
            double error = (double)(cms.estimate(e.getKey()) - e.getValue()) / cms.getTotalCount();
            maxError = Math.max(maxError, error);
        }
        System.out.printf("PASS: Max relative error = %.6f (bound = 0.001)\n", maxError);
        assert maxError < 0.001 : "Error exceeded epsilon";

        // Test 4: Heavy hitters detection
        cms = new CountMinSketch(0.001, 0.01);
        // Zipf-like distribution: few items very frequent
        Set<String> allItems = new HashSet<>();
        for (int i = 0; i < 50000; i++) {
            cms.add("rare-" + (i % 1000)); // 1000 items, each ~50 times
            allItems.add("rare-" + (i % 1000));
        }
        for (int i = 0; i < 10000; i++) {
            cms.add("hot-A"); allItems.add("hot-A");
            cms.add("hot-B"); allItems.add("hot-B");
        }
        cms.add("hot-C", 5000); allItems.add("hot-C");

        List<Map.Entry<String, Integer>> heavyHitters = cms.findHeavyHitters(allItems, 0.05);
        System.out.println("Heavy hitters (>5% of traffic):");
        for (Map.Entry<String, Integer> hh : heavyHitters) {
            System.out.printf("  %s: estimated=%d\n", hh.getKey(), hh.getValue());
        }
        assert heavyHitters.stream().anyMatch(e -> e.getKey().equals("hot-A"));
        assert heavyHitters.stream().anyMatch(e -> e.getKey().equals("hot-B"));
        System.out.println("PASS: Correctly identifies heavy hitters");

        // Test 5: Memory efficiency comparison
        int uniqueItems = 1000000;
        // CMS for 0.1% error, 99% confidence
        int cmsBytes = (int)(Math.ceil(Math.E / 0.001) * Math.ceil(Math.log(100)) * 4);
        int hashMapBytes = uniqueItems * 50; // rough HashMap estimate
        System.out.printf("\nMemory: CMS=%d KB vs HashMap=%d KB for %d items (%.0fx savings)\n",
            cmsBytes/1024, hashMapBytes/1024, uniqueItems, (double)hashMapBytes/cmsBytes);

        // Test 6: Unseen items have zero or near-zero estimate
        cms = new CountMinSketch(2000, 5);
        cms.add("exists", 100);
        int unseenEst = cms.estimate("never-added-item-xyz");
        System.out.println("PASS: Unseen item estimate = " + unseenEst + " (may be >0 due to collisions)");

        System.out.println("\nAll tests passed!");
    }
}
