import java.util.*;

/**
 * Problem 5: Top K Frequent Elements
 * Return the k most frequent elements from an array.
 *
 * Approach: Count frequencies with HashMap, then use bucket sort (index = frequency).
 * Alternative: Min-heap of size k for O(n log k).
 *
 * Time Complexity: O(n) with bucket sort
 * Space Complexity: O(n)
 *
 * Production Analogy: Trending topics calculation, hot key detection in distributed
 * caches, top-N query results for dashboards and analytics.
 */
public class Problem05_TopKFrequentElements {
    @SuppressWarnings("unchecked")
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);

        // Bucket sort: index = frequency
        List<Integer>[] buckets = new List[nums.length + 1];
        for (var entry : freq.entrySet()) {
            int f = entry.getValue();
            if (buckets[f] == null) buckets[f] = new ArrayList<>();
            buckets[f].add(entry.getKey());
        }

        int[] result = new int[k];
        int idx = 0;
        for (int i = buckets.length - 1; i >= 0 && idx < k; i--) {
            if (buckets[i] != null) {
                for (int num : buckets[i]) {
                    if (idx >= k) break;
                    result[idx++] = num;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        Problem05_TopKFrequentElements sol = new Problem05_TopKFrequentElements();
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{1,1,1,2,2,3}, 2))); // [1,2]
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{1}, 1))); // [1]
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{4,4,4,4,5,5,5,6,6,7}, 2))); // [4,5]
    }
}
