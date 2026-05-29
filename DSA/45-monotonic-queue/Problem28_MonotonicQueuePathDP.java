/**
 * Problem: Problem28 MonotonicQueuePathDP - 1D path DP where dp[i] = cost[i] + min(dp[j]) for j in [i-k,i-1].
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: 1D path DP where dp[i] = cost[i] + min(dp[j]) for j in [i-k,i-1].
 */
import java.util.*;

public class Problem28_MonotonicQueuePathDP {
    public static int minCostPath(int[] cost, int k) {
        int n = cost.length;
        int[] dp = new int[n];
        dp[0] = cost[0];
        Deque<Integer> deque = new ArrayDeque<>();
        deque.offerLast(0);
        for (int i = 1; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k) deque.pollFirst();
            dp[i] = cost[i] + dp[deque.peekFirst()];
            while (!deque.isEmpty() && dp[deque.peekLast()] >= dp[i]) deque.pollLast();
            deque.offerLast(i);
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        System.out.println(minCostPath(new int[]{1, 3, 1, 5, 2}, 2)); // 4 (1->1->2)
    }
}
