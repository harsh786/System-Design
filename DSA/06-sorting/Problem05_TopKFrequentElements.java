import java.util.*;

/**
 * Problem 5: Top K Frequent Elements
 * 
 * Given an integer array nums and integer k, return the k most frequent elements.
 * 
 * Approach: Bucket sort by frequency. Index = frequency, value = list of elements with that freq.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Finding top-k trending search queries or most accessed API endpoints
 * for cache warming decisions.
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
                for (int val : buckets[i]) {
                    if (idx < k) result[idx++] = val;
                }
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem05_TopKFrequentElements sol = new Problem05_TopKFrequentElements();
        
        System.out.println("Test 1: " + Arrays.toString(sol.topKFrequent(new int[]{1,1,1,2,2,3}, 2))); // [1,2]
        System.out.println("Test 2: " + Arrays.toString(sol.topKFrequent(new int[]{1}, 1))); // [1]
        System.out.println("Test 3: " + Arrays.toString(sol.topKFrequent(new int[]{4,4,4,4,1,1,2,2,2,3}, 2))); // [4,2]
        System.out.println("Test 4: " + Arrays.toString(sol.topKFrequent(new int[]{-1,-1,2,2,3}, 2))); // [-1,2]
    }
}
