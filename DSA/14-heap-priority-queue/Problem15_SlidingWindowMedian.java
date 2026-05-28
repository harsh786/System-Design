import java.util.*;

/**
 * Problem 15: Sliding Window Median (LeetCode 480)
 * 
 * Approach: Two heaps (max/min) with lazy deletion. Track balance between heaps.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Rolling median latency over a sliding time window for
 * real-time SLA monitoring dashboards.
 */
public class Problem15_SlidingWindowMedian {
    
    public double[] medianSlidingWindow(int[] nums, int k) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        double[] result = new double[nums.length - k + 1];
        
        for (int i = 0; i < nums.length; i++) {
            if (maxHeap.isEmpty() || nums[i] <= maxHeap.peek()) maxHeap.offer(nums[i]);
            else minHeap.offer(nums[i]);
            
            // Balance
            while (maxHeap.size() > minHeap.size() + 1) minHeap.offer(maxHeap.poll());
            while (minHeap.size() > maxHeap.size()) maxHeap.offer(minHeap.poll());
            
            if (i >= k - 1) {
                if (k % 2 == 1) result[i - k + 1] = maxHeap.peek();
                else result[i - k + 1] = ((long)maxHeap.peek() + minHeap.peek()) / 2.0;
                
                int toRemove = nums[i - k + 1];
                if (toRemove <= maxHeap.peek()) maxHeap.remove(toRemove);
                else minHeap.remove(toRemove);
                
                while (maxHeap.size() > minHeap.size() + 1) minHeap.offer(maxHeap.poll());
                while (minHeap.size() > maxHeap.size()) maxHeap.offer(minHeap.poll());
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem15_SlidingWindowMedian sol = new Problem15_SlidingWindowMedian();
        System.out.println(Arrays.toString(sol.medianSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
        // [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
    }
}
