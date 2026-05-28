/**
 * Problem: Island Perimeter (LeetCode 463)
 * Approach: DFS counting edges that touch water or boundary
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Calculating external API surface area of a service cluster
 */
public class Problem33_IslandPerimeter {
    public int islandPerimeter(int[][] grid) {
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] == 1) return dfs(grid, i, j);
        return 0;
    }

    private int dfs(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] == 0) return 1;
        if (grid[i][j] == -1) return 0;
        grid[i][j] = -1;
        return dfs(grid, i+1, j) + dfs(grid, i-1, j) + dfs(grid, i, j+1) + dfs(grid, i, j-1);
    }

    public static void main(String[] args) {
        int[][] grid = {{0,1,0,0},{1,1,1,0},{0,1,0,0},{1,1,0,0}};
        System.out.println(new Problem33_IslandPerimeter().islandPerimeter(grid)); // 16
    }
}
