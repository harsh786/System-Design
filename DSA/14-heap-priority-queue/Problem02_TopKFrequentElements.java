import java.util.*;

/**
 * Problem 2: Top K Frequent Elements (LeetCode 347)
 * 
 * Approach: Count frequencies with HashMap, then use min-heap of size K.
 * 
 * Time Complexity: O(N log K)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Finding top-K most accessed API endpoints for caching decisions,
 * or top-K error codes for incident prioritization.
 */
public class Problem02_TopKFrequentElements {
    
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        
        PriorityQueue<Map.Entry<Integer, Integer>> minHeap = 
            new PriorityQueue<>(Comparator.comparingInt(Map.Entry::getValue));
        
        for (Map.Entry<Integer, Integer> e : freq.entrySet()) {
            minHeap.offer(e);
            if (minHeap.size() > k) minHeap.poll();
        }
        
        int[] result = new int[k];
        for (int i = 0; i < k; i++) result[i] = minHeap.poll().getKey();
        return result;
    }
    
    public static void main(String[] args) {
        Problem02_TopKFrequentElements sol = new Problem02_TopKFrequentElements();
        
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{1,1,1,2,2,3}, 2))); // [2,1] or [1,2]
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{1}, 1))); // [1]
        System.out.println(Arrays.toString(sol.topKFrequent(new int[]{4,4,4,4,5,5,5,6,6,7}, 3))); // [4,5,6]
    }
}
