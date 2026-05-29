/**
 * Problem: Monotonic Queue for Prefix Sum
 * Combine prefix sums with monotonic deque for range queries.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Finding optimal batch size in streaming data processing.
 */
import java.util.*;

public class Problem14_MonotonicQueuePrefixSum {
    // Find max sum subarray of length between minLen and maxLen
    public static long maxSumBounded(int[] nums, int minLen, int maxLen) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        Deque<Integer> deque = new ArrayDeque<>();
        long ans = Long.MIN_VALUE;
        for (int i = minLen; i <= n; i++) {
            int j = i - minLen;
            while (!deque.isEmpty() && prefix[deque.peekLast()] >= prefix[j]) deque.pollLast();
            deque.offerLast(j);
            while (!deque.isEmpty() && deque.peekFirst() < i - maxLen) deque.pollFirst();
            ans = Math.max(ans, prefix[i] - prefix[deque.peekFirst()]);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(maxSumBounded(new int[]{1, -2, 3, 4, -1, 2, -3}, 2, 4)); // 8
    }
}
