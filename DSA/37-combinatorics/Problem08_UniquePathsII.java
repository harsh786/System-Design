public class Problem08_UniquePathsII {
    public int uniquePathsWithObstacles(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        long[] dp = new long[n];
        dp[0] = grid[0][0] == 0 ? 1 : 0;
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 1) { dp[j] = 0; }
                else if (j > 0) dp[j] += dp[j-1];
            }
        }
        return (int) dp[n-1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem08_UniquePathsII().uniquePathsWithObstacles(new int[][]{{0,0,0},{0,1,0},{0,0,0}}));
    }
}
