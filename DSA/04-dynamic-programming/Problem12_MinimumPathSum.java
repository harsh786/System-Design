/**
 * Problem 12: Minimum Path Sum
 * 
 * Find path from top-left to bottom-right with minimum sum (move right/down only).
 * 
 * State: dp[i][j] = min path sum to reach (i,j)
 * Recurrence: dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])
 * 
 * Time: O(m*n), Space: O(n)
 * 
 * Production Analogy: Like finding lowest-latency path through service mesh layers.
 */
public class Problem12_MinimumPathSum {

    public static int minPathSum(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[] dp = new int[n];
        dp[0] = grid[0][0];
        for (int j = 1; j < n; j++) dp[j] = dp[j - 1] + grid[0][j];
        for (int i = 1; i < m; i++) {
            dp[0] += grid[i][0];
            for (int j = 1; j < n; j++) {
                dp[j] = grid[i][j] + Math.min(dp[j], dp[j - 1]);
            }
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        System.out.println("=== Minimum Path Sum ===");
        System.out.println(minPathSum(new int[][]{{1,3,1},{1,5,1},{4,2,1}})); // 7
        System.out.println(minPathSum(new int[][]{{1,2,3},{4,5,6}})); // 12
    }
}
