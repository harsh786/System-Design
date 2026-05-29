/**
 * Problem: DP with Monotonic Deque Optimization
 * General technique: when dp[i] depends on max/min of dp[j..i-1] in bounded range, use deque.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Optimizing resource scheduling decisions with lookback window.
 */
import java.util.*;

public class Problem09_DPMonotonicDequeOptimization {
    // Generic DP optimization: dp[i] = A[i] + max(dp[j]) for j in [i-k, i-1]
    public static int[] dpWithDeque(int[] A, int k) {
        int n = A.length;
        int[] dp = new int[n];
        Deque<Integer> deque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k) deque.pollFirst();
            dp[i] = A[i] + (deque.isEmpty() ? 0 : dp[deque.peekFirst()]);
            while (!deque.isEmpty() && dp[deque.peekLast()] <= dp[i]) deque.pollLast();
            deque.offerLast(i);
        }
        return dp;
    }

    public static void main(String[] args) {
        int[] result = dpWithDeque(new int[]{3, -1, 5, -2, 4}, 2);
        System.out.println("DP values: " + Arrays.toString(result));
    }
}
