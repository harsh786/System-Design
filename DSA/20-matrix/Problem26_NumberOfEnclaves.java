import java.util.*;

/**
 * Problem 26: Number of Enclaves
 * 
 * Count land cells that cannot reach boundary.
 *
 * Approach: DFS/BFS from border land cells to mark reachable. Count remaining land.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Identifying isolated internal network segments that have no
 * external connectivity - useful for security auditing.
 */
public class Problem26_NumberOfEnclaves {

    public static int numEnclaves(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        for (int i = 0; i < m; i++) { flood(grid, i, 0); flood(grid, i, n-1); }
        for (int j = 0; j < n; j++) { flood(grid, 0, j); flood(grid, m-1, j); }
        int count = 0;
        for (int[] row : grid) for (int c : row) if (c == 1) count++;
        return count;
    }

    private static void flood(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return;
        grid[i][j] = 0;
        flood(grid, i+1, j); flood(grid, i-1, j); flood(grid, i, j+1); flood(grid, i, j-1);
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + numEnclaves(new int[][]{{0,0,0,0},{1,0,1,0},{0,1,1,0},{0,0,0,0}})); // 3
        System.out.println("Test 2: " + numEnclaves(new int[][]{{0,1,1,0},{0,0,1,0},{0,0,1,0},{0,0,0,0}})); // 0
    }
}
