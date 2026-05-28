import java.util.*;

/**
 * Problem 35: Random Pick with Weight
 * 
 * Pick index proportional to weight. Use prefix sums + binary search.
 * 
 * Approach: Build prefix sum array. Generate random in [1, totalWeight],
 * binary search for the index where prefix[i] >= random.
 * 
 * Time: O(n) init, O(log n) pick, Space: O(n)
 * 
 * Production Analogy: Weighted load balancing — routing requests to servers
 * proportional to their capacity using prefix-sum selection.
 */
public class Problem35_RandomPickWithWeight {
    private int[] prefix;
    private int total;
    private Random rand;

    public Problem35_RandomPickWithWeight(int[] w) {
        prefix = new int[w.length];
        prefix[0] = w[0];
        for (int i = 1; i < w.length; i++) prefix[i] = prefix[i-1] + w[i];
        total = prefix[w.length - 1];
        rand = new Random();
    }

    public int pickIndex() {
        int target = rand.nextInt(total) + 1;
        int lo = 0, hi = prefix.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefix[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        Problem35_RandomPickWithWeight sol = new Problem35_RandomPickWithWeight(new int[]{1, 3});
        Map<Integer, Integer> counts = new HashMap<>();
        for (int i = 0; i < 10000; i++) {
            int idx = sol.pickIndex();
            counts.merge(idx, 1, Integer::sum);
        }
        System.out.println("Distribution: " + counts); // ~25% index 0, ~75% index 1

        Problem35_RandomPickWithWeight sol2 = new Problem35_RandomPickWithWeight(new int[]{1});
        System.out.println(sol2.pickIndex()); // always 0
    }
}
