import java.util.*;

/**
 * Problem 47: Path with Maximum Gold (LeetCode 1219)
 * 
 * In a gold mine grid, find path that collects maximum gold (can't visit cell twice, can't visit 0).
 * 
 * Search Tree:
 * - Start DFS from every non-zero cell
 * - At each cell, explore 4 directions
 * 
 * Pruning Strategy:
 * - Skip cells with 0 gold
 * - Mark visited cells (set to 0, restore after)
 * 
 * Time Complexity: O(m*n * 3^(m*n)) worst case but bounded by gold cells
 * Space Complexity: O(m*n)
 * 
 * Production Analogy:
 * - Maximum value path in a weighted graph with visit-once constraint (delivery routing).
 */
public class Problem47_PathWithMaximumGold {

    private int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public int getMaximumGold(int[][] grid) {
        int max = 0;
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] != 0)
                    max = Math.max(max, dfs(grid, i, j));
        return max;
    }

    private int dfs(int[][] grid, int r, int c) {
        if (r < 0 || r >= grid.length || c < 0 || c >= grid[0].length || grid[r][c] == 0) return 0;
        int gold = grid[r][c];
        grid[r][c] = 0;
        int max = 0;
        for (int[] d : dirs) max = Math.max(max, dfs(grid, r + d[0], c + d[1]));
        grid[r][c] = gold;
        return gold + max;
    }

    public static void main(String[] args) {
        Problem47_PathWithMaximumGold sol = new Problem47_PathWithMaximumGold();

        System.out.println(sol.getMaximumGold(new int[][]{{0,6,0},{5,8,7},{0,9,0}})); // 24
        System.out.println(sol.getMaximumGold(new int[][]{{1,0,7},{2,0,6},{3,4,5},{0,3,0},{9,0,20}})); // 28
    }
}
