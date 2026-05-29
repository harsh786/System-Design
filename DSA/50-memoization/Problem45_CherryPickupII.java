import java.util.*;

public class Problem45_CherryPickupII {
    private Integer[][][] memo;

    public int cherryPickup(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        memo = new Integer[m][n][n];
        return helper(grid, 0, 0, n - 1);
    }

    private int helper(int[][] grid, int row, int c1, int c2) {
        int m = grid.length, n = grid[0].length;
        if (row == m) return 0;
        if (c1 < 0 || c1 >= n || c2 < 0 || c2 >= n) return 0;
        if (memo[row][c1][c2] != null) return memo[row][c1][c2];
        int cherries = (c1 == c2) ? grid[row][c1] : grid[row][c1] + grid[row][c2];
        int max = 0;
        for (int d1 = -1; d1 <= 1; d1++)
            for (int d2 = -1; d2 <= 1; d2++)
                max = Math.max(max, helper(grid, row + 1, c1 + d1, c2 + d2));
        memo[row][c1][c2] = cherries + max;
        return memo[row][c1][c2];
    }

    public static void main(String[] args) {
        Problem45_CherryPickupII sol = new Problem45_CherryPickupII();
        System.out.println(sol.cherryPickup(new int[][]{{3,1,1},{2,5,1},{1,5,5},{2,1,1}})); // 24
    }
}
