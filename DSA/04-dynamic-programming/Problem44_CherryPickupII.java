/**
 * Problem 44: Cherry Pickup II
 * 
 * Two robots at top row (0,0) and (0,cols-1). Move down collecting cherries.
 * Both move simultaneously, one row at a time, can go down-left, down, or down-right.
 * 
 * State: dp[c1][c2] = max cherries when robot1 at col c1, robot2 at col c2 in current row
 * Time: O(rows * cols^2 * 9), Space: O(cols^2)
 */
public class Problem44_CherryPickupII {

    public static int cherryPickup(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dp = new int[n][n];
        for (int[] row : dp) java.util.Arrays.fill(row, -1);
        dp[0][n - 1] = grid[0][0] + grid[0][n - 1];

        for (int row = 1; row < m; row++) {
            int[][] ndp = new int[n][n];
            for (int[] r : ndp) java.util.Arrays.fill(r, -1);
            for (int c1 = 0; c1 < n; c1++) {
                for (int c2 = 0; c2 < n; c2++) {
                    for (int dc1 = -1; dc1 <= 1; dc1++) {
                        for (int dc2 = -1; dc2 <= 1; dc2++) {
                            int pc1 = c1 - dc1, pc2 = c2 - dc2;
                            if (pc1 >= 0 && pc1 < n && pc2 >= 0 && pc2 < n && dp[pc1][pc2] != -1) {
                                int val = grid[row][c1] + (c1 != c2 ? grid[row][c2] : 0);
                                ndp[c1][c2] = Math.max(ndp[c1][c2], dp[pc1][pc2] + val);
                            }
                        }
                    }
                }
            }
            dp = ndp;
        }
        int max = 0;
        for (int[] row : dp) for (int v : row) max = Math.max(max, v);
        return max;
    }

    public static void main(String[] args) {
        System.out.println("=== Cherry Pickup II ===");
        System.out.println(cherryPickup(new int[][]{
            {3,1,1},{2,5,1},{1,5,5},{2,1,1}})); // 24
        System.out.println(cherryPickup(new int[][]{
            {1,0,0,0,0,0,1},{2,0,0,0,0,3,0},{2,0,9,0,0,0,0},
            {0,3,0,5,4,0,0},{1,0,2,3,0,0,6}})); // 28
    }
}
