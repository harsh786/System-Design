import java.util.*;

/**
 * Problem 10: Last Stone Weight (LeetCode 1046)
 * 
 * Approach: Max-heap. Smash two heaviest stones repeatedly.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Resource deallocation - repeatedly merging/reducing the two
 * largest memory allocations during garbage collection compaction.
 */
public class Problem10_LastStoneWeight {
    
    public int lastStoneWeight(int[] stones) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        for (int s : stones) maxHeap.offer(s);
        
        while (maxHeap.size() > 1) {
            int a = maxHeap.poll(), b = maxHeap.poll();
            if (a != b) maxHeap.offer(a - b);
        }
        return maxHeap.isEmpty() ? 0 : maxHeap.peek();
    }
    
    public static void main(String[] args) {
        Problem10_LastStoneWeight sol = new Problem10_LastStoneWeight();
        System.out.println(sol.lastStoneWeight(new int[]{2,7,4,1,8,1})); // 1
        System.out.println(sol.lastStoneWeight(new int[]{1})); // 1
        System.out.println(sol.lastStoneWeight(new int[]{3,3})); // 0
    }
}
