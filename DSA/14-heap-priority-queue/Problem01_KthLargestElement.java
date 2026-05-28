import java.util.PriorityQueue;

/**
 * Problem 1: Kth Largest Element in an Array (LeetCode 215)
 * 
 * Approach: Use a min-heap of size K. The top of the heap is the Kth largest.
 * 
 * Time Complexity: O(N log K)
 * Space Complexity: O(K)
 * 
 * Production Analogy: Top-K monitoring - finding the Kth highest latency request
 * in a stream of API calls for SLA alerting.
 */
public class Problem01_KthLargestElement {
    
    public int findKthLargest(int[] nums, int k) {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        for (int num : nums) {
            minHeap.offer(num);
            if (minHeap.size() > k) {
                minHeap.poll();
            }
        }
        return minHeap.peek();
    }
    
    public static void main(String[] args) {
        Problem01_KthLargestElement sol = new Problem01_KthLargestElement();
        
        // Test 1: Basic case
        System.out.println(sol.findKthLargest(new int[]{3,2,1,5,6,4}, 2)); // Expected: 5
        
        // Test 2: With duplicates
        System.out.println(sol.findKthLargest(new int[]{3,2,3,1,2,4,5,5,6}, 4)); // Expected: 4
        
        // Test 3: Single element
        System.out.println(sol.findKthLargest(new int[]{1}, 1)); // Expected: 1
        
        // Test 4: All same elements
        System.out.println(sol.findKthLargest(new int[]{7,7,7,7}, 2)); // Expected: 7
        
        // Test 5: Negative numbers
        System.out.println(sol.findKthLargest(new int[]{-1,-2,-3,-4}, 2)); // Expected: -2
    }
}
