/**
 * Problem 11: Unique Paths II (with obstacles)
 * 
 * Same as Unique Paths but grid has obstacles (1 = obstacle).
 * 
 * State: dp[i][j] = paths to (i,j), 0 if obstacle
 * Time: O(m*n), Space: O(n)
 */
public class Problem11_UniquePathsII {

    public static int uniquePathsWithObstacles(int[][] grid) {
        int n = grid[0].length;
        int[] dp = new int[n];
        dp[0] = grid[0][0] == 0 ? 1 : 0;
        for (int[] row : grid) {
            for (int j = 0; j < n; j++) {
                if (row[j] == 1) { dp[j] = 0; }
                else if (j > 0) { dp[j] += dp[j - 1]; }
            }
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        System.out.println("=== Unique Paths II ===");
        System.out.println(uniquePathsWithObstacles(new int[][]{{0,0,0},{0,1,0},{0,0,0}})); // 2
        System.out.println(uniquePathsWithObstacles(new int[][]{{0,1},{0,0}})); // 1
        System.out.println(uniquePathsWithObstacles(new int[][]{{1}})); // 0
    }
}
