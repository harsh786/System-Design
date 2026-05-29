/**
 * Problem: Sliding Window Minimum
 * Monotonic increasing deque - front has minimum of current window.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Rolling minimum latency for best-case performance tracking.
 */
import java.util.*;

public class Problem08_SlidingWindowMinimum {
    public static int[] minSlidingWindow(int[] nums, int k) {
        int n = nums.length;
        int[] result = new int[n - k + 1];
        Deque<Integer> deque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k + 1) deque.pollFirst();
            while (!deque.isEmpty() && nums[deque.peekLast()] > nums[i]) deque.pollLast();
            deque.offerLast(i);
            if (i >= k - 1) result[i - k + 1] = nums[deque.peekFirst()];
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(minSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3))); // [-1,-3,-3,-3,3,3]
    }
}
