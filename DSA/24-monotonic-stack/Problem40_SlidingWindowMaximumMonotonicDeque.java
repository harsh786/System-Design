import java.util.*;

/**
 * Problem 40: Sliding Window Maximum with Monotonic Deque (LeetCode 239)
 * 
 * Find maximum in each sliding window of size k.
 * 
 * Monotonic Invariant: Decreasing deque of indices. Front is always the max.
 * Remove from front if out of window. Remove from back if smaller than incoming.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Real-time max latency tracker over a sliding time window
 * for dashboard alerting.
 */
public class Problem40_SlidingWindowMaximumMonotonicDeque {
    
    public int[] maxSlidingWindow(int[] nums, int k) {
        int n = nums.length;
        int[] result = new int[n - k + 1];
        Deque<Integer> deque = new ArrayDeque<>(); // decreasing deque of indices
        
        for (int i = 0; i < n; i++) {
            // Remove elements outside window
            while (!deque.isEmpty() && deque.peekFirst() <= i - k) deque.pollFirst();
            // Maintain decreasing order
            while (!deque.isEmpty() && nums[deque.peekLast()] <= nums[i]) deque.pollLast();
            deque.offerLast(i);
            if (i >= k - 1) result[i - k + 1] = nums[deque.peekFirst()];
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem40_SlidingWindowMaximumMonotonicDeque sol = new Problem40_SlidingWindowMaximumMonotonicDeque();
        
        System.out.println(Arrays.toString(sol.maxSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3)));
        // [3,3,5,5,6,7]
        
        System.out.println(Arrays.toString(sol.maxSlidingWindow(new int[]{1}, 1)));
        // [1]
        
        System.out.println(Arrays.toString(sol.maxSlidingWindow(new int[]{9,8,7,6,5}, 3)));
        // [9,8,7]
    }
}
