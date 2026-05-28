import java.util.*;

/**
 * Problem 49: Continuous Median
 * 
 * Approach: Two heaps (same as Problem 3) but returns all running medians.
 * 
 * Time Complexity: O(N log N) total
 * Space Complexity: O(N)
 * 
 * Production Analogy: Streaming analytics pipeline computing running median
 * of transaction amounts for fraud detection thresholds.
 */
public class Problem49_ContinuousMedian {
    
    public double[] continuousMedian(int[] nums) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        double[] medians = new double[nums.length];
        
        for (int i = 0; i < nums.length; i++) {
            maxHeap.offer(nums[i]);
            minHeap.offer(maxHeap.poll());
            if (minHeap.size() > maxHeap.size()) maxHeap.offer(minHeap.poll());
            
            if (maxHeap.size() > minHeap.size()) medians[i] = maxHeap.peek();
            else medians[i] = (maxHeap.peek() + minHeap.peek()) / 2.0;
        }
        return medians;
    }
    
    public static void main(String[] args) {
        Problem49_ContinuousMedian sol = new Problem49_ContinuousMedian();
        System.out.println(Arrays.toString(sol.continuousMedian(new int[]{5, 2, 8, 1, 9})));
        // [5.0, 3.5, 5.0, 3.5, 5.0]
        System.out.println(Arrays.toString(sol.continuousMedian(new int[]{1, 2, 3, 4})));
        // [1.0, 1.5, 2.0, 2.5]
    }
}
