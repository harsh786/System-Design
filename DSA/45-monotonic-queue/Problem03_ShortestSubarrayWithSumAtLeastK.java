/**
 * Problem: Shortest Subarray with Sum at Least K (LC 862)
 * Find shortest subarray with sum >= k (may have negative numbers).
 * 
 * Approach: Prefix sums + monotonic deque. For each i, find smallest j where
 * prefix[i] - prefix[j] >= k. Deque maintains increasing prefix sums.
 * Time: O(n) | Space: O(n)
 * 
 * Production Analogy: Finding minimum time window where cumulative revenue meets target.
 */
import java.util.*;

public class Problem03_ShortestSubarrayWithSumAtLeastK {
    public static int shortestSubarray(int[] nums, int k) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];

        Deque<Integer> deque = new ArrayDeque<>();
        int ans = Integer.MAX_VALUE;

        for (int i = 0; i <= n; i++) {
            while (!deque.isEmpty() && prefix[i] - prefix[deque.peekFirst()] >= k) {
                ans = Math.min(ans, i - deque.pollFirst());
            }
            while (!deque.isEmpty() && prefix[deque.peekLast()] >= prefix[i]) {
                deque.pollLast();
            }
            deque.offerLast(i);
        }
        return ans == Integer.MAX_VALUE ? -1 : ans;
    }

    public static void main(String[] args) {
        System.out.println(shortestSubarray(new int[]{2, -1, 2}, 3)); // 3
        System.out.println(shortestSubarray(new int[]{1}, 1)); // 1
        System.out.println(shortestSubarray(new int[]{84, -37, 32, 40, 95}, 167)); // 3
    }
}
