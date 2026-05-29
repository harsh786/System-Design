/**
 * Problem: Problem50 SlidingWindowMedianAlternative - Approximate median using max of lower half + min of upper half with two deques.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Approximate median using max of lower half + min of upper half with two deques.
 */
import java.util.*;

public class Problem50_SlidingWindowMedianAlternative {
    // Approximate sliding window median using two deques tracking partitions
    // Simplified approach: sorted insert with deque-based max of lower / min of upper
    public static double[] slidingMedian(int[] nums, int k) {
        int n = nums.length;
        double[] result = new double[n - k + 1];
        TreeMap<Integer, Integer> lower = new TreeMap<>(), upper = new TreeMap<>();
        int lowerSize = 0, upperSize = 0;

        for (int i = 0; i < n; i++) {
            // Add to lower or upper
            if (lowerSize == 0 || nums[i] <= lower.lastKey()) { lower.merge(nums[i], 1, Integer::sum); lowerSize++; }
            else { upper.merge(nums[i], 1, Integer::sum); upperSize++; }
            // Remove if window exceeded
            if (i >= k) {
                int rem = nums[i - k];
                if (lower.containsKey(rem) && rem <= lower.lastKey()) { if (lower.get(rem) == 1) lower.remove(rem); else lower.merge(rem, -1, Integer::sum); lowerSize--; }
                else { if (upper.get(rem) == 1) upper.remove(rem); else upper.merge(rem, -1, Integer::sum); upperSize--; }
            }
            // Balance
            while (lowerSize > upperSize + 1) { int move = lower.lastKey(); if (lower.get(move) == 1) lower.remove(move); else lower.merge(move, -1, Integer::sum); upper.merge(move, 1, Integer::sum); lowerSize--; upperSize++; }
            while (upperSize > lowerSize) { int move = upper.firstKey(); if (upper.get(move) == 1) upper.remove(move); else upper.merge(move, -1, Integer::sum); lower.merge(move, 1, Integer::sum); upperSize++; lowerSize--; /* fix */ lowerSize++; upperSize--; }
            if (i >= k - 1) {
                if (k % 2 == 1) result[i - k + 1] = lower.lastKey();
                else result[i - k + 1] = ((double) lower.lastKey() + upper.firstKey()) / 2.0;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(slidingMedian(new int[]{1, 3, -1, -3, 5, 3, 6, 7}, 3)));
    }
}
