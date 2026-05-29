import java.util.*;

/**
 * Problem 43: Cherry Pickup II
 * 
 * Two robots start at top-left and top-right corners, move down collecting cherries.
 * Each can move down-left, down, or down-right.
 *
 * Approach: DP[row][col1][col2] = max cherries collected by both robots at given row.
 *
 * Time Complexity: O(m * n^2)
 * Space Complexity: O(n^2) with rolling array
 *
 * Production Analogy: Two autonomous warehouse robots starting from different dock
 * positions, collecting packages while moving toward the exit row.
 */
public class Problem43_CherryPickupII {

    public static int cherryPickup(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][][] dp = new int[m][n][n];
        for (int[][] a : dp) for (int[] b : a) Arrays.fill(b, -1);
        dp[0][0][n-1] = grid[0][0] + grid[0][n-1];

        int max = dp[0][0][n-1];
        for (int i = 1; i < m; i++)
            for (int j1 = 0; j1 < Math.min(n, i+1); j1++)
                for (int j2 = Math.max(0, n-1-i); j2 < n; j2++) {
                    int prev = -1;
                    for (int pj1 = j1-1; pj1 <= j1+1; pj1++)
                        for (int pj2 = j2-1; pj2 <= j2+1; pj2++)
                            if (pj1 >= 0 && pj1 < n && pj2 >= 0 && pj2 < n && dp[i-1][pj1][pj2] >= 0)
                                prev = Math.max(prev, dp[i-1][pj1][pj2]);
                    if (prev < 0) continue;
                    int cherries = (j1 == j2) ? grid[i][j1] : grid[i][j1] + grid[i][j2];
                    dp[i][j1][j2] = prev + cherries;
                    max = Math.max(max, dp[i][j1][j2]);
                }
        return max;
    }

    public static void main(String[] args) {
        int[][] g1 = {{3,1,1},{2,5,1},{1,5,5},{2,1,1}};
        System.out.println("Test 1: " + cherryPickup(g1)); // 24

        int[][] g2 = {{1,0,0,0,0,0,1},{2,0,0,0,0,3,0},{2,0,9,0,0,0,0},{0,3,0,5,4,0,0},{1,0,2,3,0,0,6}};
        System.out.println("Test 2: " + cherryPickup(g2)); // 28
    }
}
