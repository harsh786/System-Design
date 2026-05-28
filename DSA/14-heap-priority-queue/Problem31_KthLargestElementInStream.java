import java.util.*;

/**
 * Problem 31: Kth Largest Element in a Stream (LeetCode 703)
 * 
 * Approach: Min-heap of size K. Top is always the Kth largest.
 * 
 * Time Complexity: O(log K) per add, O(N log K) constructor
 * Space Complexity: O(K)
 * 
 * Production Analogy: Real-time leaderboard maintaining top-K scores,
 * or monitoring Kth highest resource consumer for alerts.
 */
public class Problem31_KthLargestElementInStream {
    
    private PriorityQueue<Integer> minHeap = new PriorityQueue<>();
    private int k;
    
    public Problem31_KthLargestElementInStream(int k, int[] nums) {
        this.k = k;
        for (int n : nums) add(n);
    }
    
    public int add(int val) {
        minHeap.offer(val);
        if (minHeap.size() > k) minHeap.poll();
        return minHeap.peek();
    }
    
    public static void main(String[] args) {
        Problem31_KthLargestElementInStream kl = new Problem31_KthLargestElementInStream(3, new int[]{4,5,8,2});
        System.out.println(kl.add(3));  // 4
        System.out.println(kl.add(5));  // 5
        System.out.println(kl.add(10)); // 5
        System.out.println(kl.add(9));  // 8
        System.out.println(kl.add(4));  // 8
    }
}
