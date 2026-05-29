/**
 * Problem: Max Subarray with Length Constraint
 * Prefix sums + monotonic deque for min prefix in window.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Find best-performing time interval within bounded duration.
 */
import java.util.*;

public class Problem10_MaxSubarrayLengthConstraint {
    // Max subarray sum where length <= maxLen
    public static long maxSubarrayBounded(int[] nums, int maxLen) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        Deque<Integer> deque = new ArrayDeque<>();
        long ans = Long.MIN_VALUE;
        for (int i = 1; i <= n; i++) {
            int start = i - maxLen;
            if (start >= 0) {
                while (!deque.isEmpty() && prefix[deque.peekLast()] >= prefix[start]) deque.pollLast();
                deque.offerLast(start);
            }
            while (!deque.isEmpty() && deque.peekFirst() < i - maxLen) deque.pollFirst();
            if (!deque.isEmpty()) ans = Math.max(ans, prefix[i] - prefix[deque.peekFirst()]);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(maxSubarrayBounded(new int[]{1, -2, 3, 4, -1, 2}, 3)); // 7 (3+4)
    }
}
