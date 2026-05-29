import java.util.*;

public class Problem18_MinimumPathSum {
    private Integer[][] memo;

    public int minPathSum(int[][] grid) {
        memo = new Integer[grid.length][grid[0].length];
        return helper(grid, 0, 0);
    }

    private int helper(int[][] grid, int i, int j) {
        if (i == grid.length - 1 && j == grid[0].length - 1) return grid[i][j];
        if (i >= grid.length || j >= grid[0].length) return Integer.MAX_VALUE;
        if (memo[i][j] != null) return memo[i][j];
        memo[i][j] = grid[i][j] + Math.min(helper(grid, i + 1, j), helper(grid, i, j + 1));
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem18_MinimumPathSum sol = new Problem18_MinimumPathSum();
        System.out.println(sol.minPathSum(new int[][]{{1,3,1},{1,5,1},{4,2,1}})); // 7
    }
}
