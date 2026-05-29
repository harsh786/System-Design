import java.util.*;

/**
 * Problem 27: Closed Island
 * 
 * Count islands (0s) completely surrounded by water (1s) - not touching border.
 *
 * Approach: Flood border-connected 0s first, then count remaining island components.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Finding completely enclosed zones in a facility layout -
 * rooms with no external exits (for ventilation planning).
 */
public class Problem27_ClosedIsland {

    public static int closedIsland(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        for (int i = 0; i < m; i++) { fill(grid, i, 0); fill(grid, i, n-1); }
        for (int j = 0; j < n; j++) { fill(grid, 0, j); fill(grid, m-1, j); }
        int count = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 0) { count++; fill(grid, i, j); }
        return count;
    }

    private static void fill(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 0) return;
        grid[i][j] = 1;
        fill(grid, i+1, j); fill(grid, i-1, j); fill(grid, i, j+1); fill(grid, i, j-1);
    }

    public static void main(String[] args) {
        int[][] g = {{1,1,1,1,1,1,1,0},{1,0,0,0,0,1,1,0},{1,0,1,0,1,1,1,0},{1,0,0,0,0,1,0,1},{1,1,1,1,1,1,1,0}};
        System.out.println("Test 1: " + closedIsland(g)); // 2
        int[][] g2 = {{0,0,1,0,0},{0,1,0,1,0},{0,1,1,1,0}};
        System.out.println("Test 2: " + closedIsland(g2)); // 1
    }
}
