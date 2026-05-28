/**
 * Problem 10: Unique Paths
 * 
 * Robot on m x n grid, top-left to bottom-right, can only move right or down.
 * 
 * State: dp[i][j] = number of paths to reach (i,j)
 * Recurrence: dp[i][j] = dp[i-1][j] + dp[i][j-1]
 * 
 * Time: O(m*n), Space: O(n) optimized
 * 
 * Production Analogy: Like counting valid request routing paths through a layered
 * microservice architecture where requests can only go to the next layer.
 */
public class Problem10_UniquePaths {

    public static int uniquePaths(int m, int n) {
        int[] dp = new int[n];
        java.util.Arrays.fill(dp, 1);
        for (int i = 1; i < m; i++) {
            for (int j = 1; j < n; j++) {
                dp[j] += dp[j - 1];
            }
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        System.out.println("=== Unique Paths ===");
        System.out.println(uniquePaths(3, 7)); // 28
        System.out.println(uniquePaths(3, 2)); // 3
        System.out.println(uniquePaths(1, 1)); // 1
    }
}
