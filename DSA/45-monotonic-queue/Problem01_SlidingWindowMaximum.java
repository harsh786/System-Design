/**
 * Problem: Sliding Window Maximum (LC 239)
 * Given array and window size k, return max of each window.
 * 
 * Approach: Monotonic decreasing deque - front always has max of current window.
 * Remove elements outside window from front, remove smaller elements from back.
 * Time Complexity: O(n) - each element added/removed at most once
 * Space Complexity: O(k)
 * 
 * Production Analogy: Rolling max latency metric over a time window for SLA monitoring.
 */
import java.util.*;

public class Problem01_SlidingWindowMaximum {
    public static int[] maxSlidingWindow(int[] nums, int k) {
        if (nums == null || nums.length == 0) return new int[0];
        int n = nums.length;
        int[] result = new int[n - k + 1];
        Deque<Integer> deque = new ArrayDeque<>(); // stores indices

        for (int i = 0; i < n; i++) {
            // Remove elements outside window
            while (!deque.isEmpty() && deque.peekFirst() < i - k + 1) deque.pollFirst();
            // Remove smaller elements from back
            while (!deque.isEmpty() && nums[deque.peekLast()] < nums[i]) deque.pollLast();
            deque.offerLast(i);
            if (i >= k - 1) result[i - k + 1] = nums[deque.peekFirst()];
        }
        return result;
    }

    public static void main(String[] args) {
        int[] nums = {1, 3, -1, -3, 5, 3, 6, 7};
        System.out.println(Arrays.toString(maxSlidingWindow(nums, 3))); // [3,3,5,5,6,7]
    }
}
