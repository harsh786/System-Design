import java.util.*;

/**
 * Problem 15: Unique Paths
 * 
 * Robot at top-left, can only move right or down. Count unique paths to bottom-right.
 *
 * Approach: DP. dp[i][j] = dp[i-1][j] + dp[i][j-1]. Can optimize to 1D array.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Counting routing paths in a grid network, or enumerating
 * possible execution paths in a DAG-based workflow scheduler.
 */
public class Problem15_UniquePaths {

    public static int uniquePaths(int m, int n) {
        int[] dp = new int[n];
        Arrays.fill(dp, 1);
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                dp[j] += dp[j-1];
        return dp[n-1];
    }

    public static void main(String[] args) {
        System.out.println("Test 1 (3,7): " + uniquePaths(3, 7)); // 28
        System.out.println("Test 2 (3,2): " + uniquePaths(3, 2)); // 3
        System.out.println("Test 3 (1,1): " + uniquePaths(1, 1)); // 1
        System.out.println("Test 4 (7,3): " + uniquePaths(7, 3)); // 28
    }
}
