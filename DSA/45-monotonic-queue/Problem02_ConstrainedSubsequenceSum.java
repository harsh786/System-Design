/**
 * Problem: Constrained Subsequence Sum (LC 1425)
 * Max sum subsequence where adjacent elements differ by at most k indices.
 * 
 * Approach: DP + monotonic deque. dp[i] = nums[i] + max(dp[j]) for j in [i-k, i-1].
 * Deque maintains max dp values in window of size k.
 * Time: O(n) | Space: O(n)
 * 
 * Production Analogy: Optimal resource allocation with constraint on how far apart selections can be.
 */
import java.util.*;

public class Problem02_ConstrainedSubsequenceSum {
    public static int constrainedSubsetSum(int[] nums, int k) {
        int n = nums.length;
        int[] dp = new int[n];
        Deque<Integer> deque = new ArrayDeque<>();
        int ans = Integer.MIN_VALUE;

        for (int i = 0; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k) deque.pollFirst();
            dp[i] = nums[i] + (deque.isEmpty() ? 0 : Math.max(0, dp[deque.peekFirst()]));
            while (!deque.isEmpty() && dp[deque.peekLast()] <= dp[i]) deque.pollLast();
            deque.offerLast(i);
            ans = Math.max(ans, dp[i]);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(constrainedSubsetSum(new int[]{10, 2, -10, 5, 20}, 2)); // 37
        System.out.println(constrainedSubsetSum(new int[]{-1, -2, -3}, 1)); // -1
    }
}
