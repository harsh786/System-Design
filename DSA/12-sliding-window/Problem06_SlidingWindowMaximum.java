import java.util.*;
/**
 * Problem 6: Sliding Window Maximum (LeetCode 239)
 * 
 * Approach: Monotonic deque maintaining decreasing order of values.
 * Window invariant: deque front is always the max of current window.
 * Elements are removed from back if smaller than incoming element.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Like maintaining peak QPS metric over a rolling time window
 * for auto-scaling decisions.
 */
public class Problem06_SlidingWindowMaximum {
    public static int[] maxSlidingWindow(int[] nums, int k) {
        if (nums == null || nums.length == 0) return new int[0];
        int[] result = new int[nums.length - k + 1];
        Deque<Integer> deque = new ArrayDeque<>(); // stores indices
        for (int i = 0; i < nums.length; i++) {
            // Remove elements outside window
            while (!deque.isEmpty() && deque.peekFirst() < i - k + 1) {
                deque.pollFirst();
            }
            // Remove smaller elements from back
            while (!deque.isEmpty() && nums[deque.peekLast()] < nums[i]) {
                deque.pollLast();
            }
            deque.offerLast(i);
            if (i >= k - 1) {
                result[i - k + 1] = nums[deque.peekFirst()];
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(maxSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7}, 3))); // [3,3,5,5,6,7]
        System.out.println(Arrays.toString(maxSlidingWindow(new int[]{1}, 1))); // [1]
        System.out.println(Arrays.toString(maxSlidingWindow(new int[]{9,11}, 2))); // [11]
        System.out.println(Arrays.toString(maxSlidingWindow(new int[]{4,-2}, 2))); // [4]
    }
}
