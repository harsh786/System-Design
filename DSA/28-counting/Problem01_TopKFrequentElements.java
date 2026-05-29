/**
 * Problem: Top K Frequent Elements (LeetCode 347)
 * Approach: Bucket sort by frequency
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Hot key detection in cache systems, trending topics
 */
import java.util.*;
public class Problem01_TopKFrequentElements {
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        List<Integer>[] buckets = new List[nums.length + 1];
        for (int i = 0; i < buckets.length; i++) buckets[i] = new ArrayList<>();
        for (var e : freq.entrySet()) buckets[e.getValue()].add(e.getKey());
        int[] res = new int[k];
        int idx = 0;
        for (int i = buckets.length-1; i >= 0 && idx < k; i--)
            for (int val : buckets[i]) { res[idx++] = val; if (idx == k) break; }
        return res;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem01_TopKFrequentElements()
            .topKFrequent(new int[]{1,1,1,2,2,3}, 2))); // [1,2]
    }
}
