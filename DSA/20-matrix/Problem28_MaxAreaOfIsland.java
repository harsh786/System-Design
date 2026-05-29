import java.util.*;

/**
 * Problem 28: Max Area of Island
 * 
 * Find the island with maximum area (number of connected 1-cells).
 *
 * Approach: DFS on each unvisited land cell, track area.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Finding the largest connected cluster in a server mesh -
 * useful for capacity planning or identifying the biggest failure domain.
 */
public class Problem28_MaxAreaOfIsland {

    public static int maxAreaOfIsland(int[][] grid) {
        int max = 0;
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] == 1) max = Math.max(max, dfs(grid, i, j));
        return max;
    }

    private static int dfs(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return 0;
        grid[i][j] = 0;
        return 1 + dfs(grid, i+1, j) + dfs(grid, i-1, j) + dfs(grid, i, j+1) + dfs(grid, i, j-1);
    }

    public static void main(String[] args) {
        int[][] g = {{0,0,1,0,0,0,0,1,0,0,0,0,0},{0,0,0,0,0,0,0,1,1,1,0,0,0},{0,1,1,0,1,0,0,0,0,0,0,0,0},{0,1,0,0,1,1,0,0,1,0,1,0,0},{0,1,0,0,1,1,0,0,1,1,1,0,0},{0,0,0,0,0,0,0,0,0,0,1,0,0},{0,0,0,0,0,0,0,1,1,1,0,0,0},{0,0,0,0,0,0,0,1,1,0,0,0,0}};
        System.out.println("Test 1: " + maxAreaOfIsland(g)); // 6
        System.out.println("Test 2: " + maxAreaOfIsland(new int[][]{{0,0,0}})); // 0
    }
}
