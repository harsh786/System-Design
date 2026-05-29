import java.util.*;

/**
 * Problem 42: Cherry Pickup
 * 
 * Grid with cherries (1), empty (0), thorns (-1). Go from (0,0) to (n-1,n-1) and back.
 * Maximize cherries collected. Equivalent to two people going from (0,0) to (n-1,n-1).
 *
 * Approach: DP with two simultaneous paths. State: (r1, c1, r2) where c2 = r1+c1-r2.
 * Both move simultaneously (same total steps).
 *
 * Time Complexity: O(n^3)
 * Space Complexity: O(n^3)
 *
 * Production Analogy: Two robots collecting items in a warehouse, maximizing total
 * items picked while avoiding double-counting shared cells.
 */
public class Problem42_CherryPickup {

    public static int cherryPickup(int[][] grid) {
        int n = grid.length;
        int[][][] dp = new int[n][n][n];
        for (int[][] a : dp) for (int[] b : a) Arrays.fill(b, Integer.MIN_VALUE);
        dp[0][0][0] = grid[0][0];

        for (int r1 = 0; r1 < n; r1++)
            for (int c1 = 0; c1 < n; c1++)
                for (int r2 = 0; r2 < n; r2++) {
                    int c2 = r1 + c1 - r2;
                    if (c2 < 0 || c2 >= n || grid[r1][c1] == -1 || grid[r2][c2] == -1) continue;
                    if (dp[r1][c1][r2] == Integer.MIN_VALUE) continue;
                    int val = dp[r1][c1][r2];
                    // Try all 4 combinations of moves for both paths
                    int[][] moves = {{0,1,0},{0,1,1},{1,0,0},{1,0,1}};
                    for (int[] m : moves) {
                        int nr1 = r1+m[0], nc1 = c1+(1-m[0])*(m[1]==1?1:0)+(m[0]==1?0:1)-1+m[0];
                        // Simpler: enumerate explicitly
                    }
                }
        // Cleaner implementation:
        return solve(grid);
    }

    private static int solve(int[][] grid) {
        int n = grid.length;
        // dp[step][r1][r2] = max cherries when both have taken 'step' steps
        int[][][] dp = new int[2*n-1][n][n];
        for (int[][] a : dp) for (int[] b : a) Arrays.fill(b, -1);
        dp[0][0][0] = grid[0][0];

        for (int k = 1; k < 2*n-1; k++)
            for (int r1 = Math.max(0, k-n+1); r1 <= Math.min(n-1, k); r1++)
                for (int r2 = Math.max(0, k-n+1); r2 <= Math.min(n-1, k); r2++) {
                    int c1 = k - r1, c2 = k - r2;
                    if (grid[r1][c1] == -1 || grid[r2][c2] == -1) continue;
                    int cherries = grid[r1][c1];
                    if (r1 != r2) cherries += grid[r2][c2];
                    int prev = -1;
                    // 4 previous states
                    for (int pr1 : new int[]{r1, r1-1})
                        for (int pr2 : new int[]{r2, r2-1})
                            if (pr1 >= 0 && pr2 >= 0 && k-1-pr1 >= 0 && k-1-pr1 < n && k-1-pr2 >= 0 && k-1-pr2 < n)
                                if (dp[k-1][pr1][pr2] >= 0)
                                    prev = Math.max(prev, dp[k-1][pr1][pr2]);
                    if (prev >= 0) dp[k][r1][r2] = prev + cherries;
                }
        return Math.max(0, dp[2*n-2][n-1][n-1]);
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + cherryPickup(new int[][]{{0,1,-1},{1,0,-1},{1,1,1}})); // 5
        System.out.println("Test 2: " + cherryPickup(new int[][]{{1,1,-1},{1,-1,1},{-1,1,1}})); // 0
    }
}
