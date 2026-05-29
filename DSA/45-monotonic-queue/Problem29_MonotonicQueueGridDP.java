/**
 * Problem: Problem29 MonotonicQueueGridDP - 2D grid DP with bounded movement optimized by monotonic deque per row/col.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: 2D grid DP with bounded movement optimized by monotonic deque per row/col.
 */
import java.util.*;

public class Problem29_MonotonicQueueGridDP {
    // Min cost path in grid where you can move at most k steps right or down from any cell
    public static int minCostGrid(int[][] grid, int k) {
        int m = grid.length, n = grid[0].length;
        int[][] dp = new int[m][n];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE);
        dp[0][0] = grid[0][0];
        // Process rows
        for (int i = 0; i < m; i++) {
            Deque<Integer> deque = new ArrayDeque<>();
            for (int j = (i == 0 ? 1 : 0); j < n; j++) {
                if (dp[i][j] != Integer.MAX_VALUE) {
                    while (!deque.isEmpty() && dp[i][deque.peekLast()] >= dp[i][j]) deque.pollLast();
                    deque.offerLast(j);
                }
                // Also consider from row above
                if (i > 0 && dp[i-1][j] != Integer.MAX_VALUE) dp[i][j] = Math.min(dp[i][j], dp[i-1][j] + grid[i][j]);
            }
            deque.clear();
            for (int j = 0; j < n; j++) {
                while (!deque.isEmpty() && deque.peekFirst() < j - k) deque.pollFirst();
                if (!deque.isEmpty() && dp[i][deque.peekFirst()] != Integer.MAX_VALUE)
                    dp[i][j] = Math.min(dp[i][j], dp[i][deque.peekFirst()] + grid[i][j]);
                while (!deque.isEmpty() && dp[i][deque.peekLast()] >= dp[i][j]) deque.pollLast();
                deque.offerLast(j);
            }
        }
        return dp[m-1][n-1];
    }

    public static void main(String[] args) {
        int[][] grid = {{1,2,3},{4,1,2},{3,2,1}};
        System.out.println(minCostGrid(grid, 2)); 
    }
}
