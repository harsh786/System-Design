/**
 * Problem: Problem47 MinCostReachEndDequeDP - Min cost to reach end with jump up to k steps, deque for min DP.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Min cost to reach end with jump up to k steps, deque for min DP.
 */
import java.util.*;

public class Problem47_MinCostReachEndDequeDP {
    public static int minCost(int[] cost, int k) {
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
        System.out.println(minCost(new int[]{1, 100, 1, 1, 100, 1}, 2)); // 4
    }
}
