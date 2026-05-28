/**
 * Problem 43: Cherry Pickup
 * 
 * n x n grid, go from (0,0) to (n-1,n-1) and back. Collect max cherries.
 * Trick: Model as two people going from (0,0) to (n-1,n-1) simultaneously.
 * 
 * State: dp[r1][c1][r2] (c2 = r1+c1-r2 since steps are same)
 * Time: O(n^3), Space: O(n^3)
 */
public class Problem43_CherryPickup {

    public static int cherryPickup(int[][] grid) {
        int n = grid.length;
        int[][][] dp = new int[n][n][n];
        for (int[][] a : dp) for (int[] b : a) java.util.Arrays.fill(b, Integer.MIN_VALUE);
        dp[0][0][0] = grid[0][0];
        for (int step = 1; step < 2 * n - 2; step++) {
            int[][][] ndp = new int[n][n][n];
            for (int[][] a : ndp) for (int[] b : a) java.util.Arrays.fill(b, Integer.MIN_VALUE);
            for (int r1 = Math.max(0, step - n + 1); r1 <= Math.min(n - 1, step); r1++) {
                for (int r2 = Math.max(0, step - n + 1); r2 <= Math.min(n - 1, step); r2++) {
                    int c1 = step - r1, c2 = step - r2;
                    if (c1 < 0 || c1 >= n || c2 < 0 || c2 >= n) continue;
                    if (grid[r1][c1] == -1 || grid[r2][c2] == -1) continue;
                    int val = grid[r1][c1];
                    if (r1 != r2) val += grid[r2][c2];
                    int best = Integer.MIN_VALUE;
                    // Previous states: both could have come from up or left
                    for (int pr1 : new int[]{r1, r1 - 1}) {
                        for (int pr2 : new int[]{r2, r2 - 1}) {
                            if (pr1 >= 0 && pr2 >= 0 && dp[pr1][step - 1 - pr1 >= 0 ? pr1 : 0][pr2] != Integer.MIN_VALUE) {
                                int pc1 = step - 1 - pr1;
                                if (pc1 >= 0 && pc1 < n && dp[pr1][pr2].length > 0) {
                                    // simplified access
                                }
                            }
                        }
                    }
                    // Let me redo with cleaner 3D approach
                }
            }
        }
        // Cleaner implementation below
        return cherryPickupClean(grid);
    }

    public static int cherryPickupClean(int[][] grid) {
        int n = grid.length;
        // dp[r1][r2] for a given step, c1=step-r1, c2=step-r2
        int[][] dp = new int[n][n];
        for (int[] row : dp) java.util.Arrays.fill(row, Integer.MIN_VALUE);
        dp[0][0] = grid[0][0];
        
        for (int step = 1; step <= 2 * n - 2; step++) {
            int[][] ndp = new int[n][n];
            for (int[] row : ndp) java.util.Arrays.fill(row, Integer.MIN_VALUE);
            for (int r1 = Math.min(n - 1, step); r1 >= Math.max(0, step - n + 1); r1--) {
                for (int r2 = Math.min(n - 1, step); r2 >= Math.max(0, step - n + 1); r2--) {
                    int c1 = step - r1, c2 = step - r2;
                    if (c1 >= n || c2 >= n) continue;
                    if (grid[r1][c1] == -1 || grid[r2][c2] == -1) continue;
                    int val = grid[r1][c1];
                    if (r1 != r2) val += grid[r2][c2];
                    int best = Integer.MIN_VALUE;
                    // 4 combinations of previous moves
                    for (int pr1 : new int[]{r1, r1 - 1}) {
                        for (int pr2 : new int[]{r2, r2 - 1}) {
                            if (pr1 >= 0 && pr2 >= 0 && dp[pr1][pr2] != Integer.MIN_VALUE) {
                                best = Math.max(best, dp[pr1][pr2]);
                            }
                        }
                    }
                    if (best != Integer.MIN_VALUE) ndp[r1][r2] = best + val;
                }
            }
            dp = ndp;
        }
        return Math.max(0, dp[n - 1][n - 1]);
    }

    public static void main(String[] args) {
        System.out.println("=== Cherry Pickup ===");
        System.out.println(cherryPickupClean(new int[][]{
            {0,1,-1},{1,0,-1},{1,1,1}})); // 5
        System.out.println(cherryPickupClean(new int[][]{{1,1},{1,1}})); // 4
    }
}
