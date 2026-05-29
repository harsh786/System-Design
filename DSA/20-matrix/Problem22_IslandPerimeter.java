import java.util.*;

/**
 * Problem 22: Island Perimeter
 * 
 * Grid with 1=land, 0=water. Calculate perimeter of the island.
 *
 * Approach: For each land cell, add 4 minus number of adjacent land cells.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Calculating the boundary/edge length of a geographic region
 * for fencing cost estimation or network perimeter firewall rules count.
 */
public class Problem22_IslandPerimeter {

    public static int islandPerimeter(int[][] grid) {
        int perimeter = 0;
        int m = grid.length, n = grid[0].length;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) {
                    perimeter += 4;
                    if (i > 0 && grid[i-1][j] == 1) perimeter -= 2;
                    if (j > 0 && grid[i][j-1] == 1) perimeter -= 2;
                }
        return perimeter;
    }

    public static void main(String[] args) {
        int[][] g = {{0,1,0,0},{1,1,1,0},{0,1,0,0},{1,1,0,0}};
        System.out.println("Test 1: " + islandPerimeter(g)); // 16
        System.out.println("Test 2: " + islandPerimeter(new int[][]{{1}})); // 4
        System.out.println("Test 3: " + islandPerimeter(new int[][]{{1,0}})); // 4
    }
}
