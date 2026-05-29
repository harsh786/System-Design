import java.util.*;

public class Problem23_UniquePathsII {
    private Integer[][] memo;

    public int uniquePathsWithObstacles(int[][] grid) {
        memo = new Integer[grid.length][grid[0].length];
        return helper(grid, 0, 0);
    }

    private int helper(int[][] grid, int i, int j) {
        if (i >= grid.length || j >= grid[0].length || grid[i][j] == 1) return 0;
        if (i == grid.length - 1 && j == grid[0].length - 1) return 1;
        if (memo[i][j] != null) return memo[i][j];
        memo[i][j] = helper(grid, i + 1, j) + helper(grid, i, j + 1);
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem23_UniquePathsII sol = new Problem23_UniquePathsII();
        System.out.println(sol.uniquePathsWithObstacles(new int[][]{{0,0,0},{0,1,0},{0,0,0}})); // 2
    }
}
