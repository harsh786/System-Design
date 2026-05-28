import java.util.*;

/**
 * Problem 44: Reduce Array Size to The Half (LeetCode 1338)
 * 
 * Approach: Count frequencies, max-heap. Greedily remove most frequent elements first.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Cache eviction strategy - determining minimum number of
 * unique keys to evict to free up 50% of cache capacity.
 */
public class Problem44_ReduceArraySizeToHalf {
    
    public int minSetSize(int[] arr) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int a : arr) freq.merge(a, 1, Integer::sum);
        
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        maxHeap.addAll(freq.values());
        
        int removed = 0, count = 0, target = arr.length / 2;
        while (removed < target) {
            removed += maxHeap.poll();
            count++;
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem44_ReduceArraySizeToHalf sol = new Problem44_ReduceArraySizeToHalf();
        System.out.println(sol.minSetSize(new int[]{3,3,3,3,5,5,5,2,2,7})); // 2
        System.out.println(sol.minSetSize(new int[]{7,7,7,7,7,7})); // 1
    }
}
