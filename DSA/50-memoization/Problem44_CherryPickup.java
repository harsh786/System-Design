import java.util.*;

public class Problem44_CherryPickup {
    private Integer[][][] memo;

    public int cherryPickup(int[][] grid) {
        int n = grid.length;
        memo = new Integer[n][n][n];
        return Math.max(0, helper(grid, 0, 0, 0));
    }

    private int helper(int[][] grid, int r1, int c1, int r2) {
        int n = grid.length;
        int c2 = r1 + c1 - r2;
        if (r1 >= n || c1 >= n || r2 >= n || c2 >= n || grid[r1][c1] == -1 || grid[r2][c2] == -1) return Integer.MIN_VALUE;
        if (r1 == n - 1 && c1 == n - 1) return grid[r1][c1];
        if (memo[r1][c1][r2] != null) return memo[r1][c1][r2];
        int cherries = (r1 == r2 && c1 == c2) ? grid[r1][c1] : grid[r1][c1] + grid[r2][c2];
        int max = Math.max(Math.max(helper(grid, r1+1, c1, r2+1), helper(grid, r1+1, c1, r2)),
                          Math.max(helper(grid, r1, c1+1, r2+1), helper(grid, r1, c1+1, r2)));
        memo[r1][c1][r2] = (max == Integer.MIN_VALUE) ? Integer.MIN_VALUE : cherries + max;
        return memo[r1][c1][r2];
    }

    public static void main(String[] args) {
        Problem44_CherryPickup sol = new Problem44_CherryPickup();
        System.out.println(sol.cherryPickup(new int[][]{{0,1,-1},{1,0,-1},{1,1,1}})); // 5
    }
}
