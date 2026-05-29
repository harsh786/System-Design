import java.util.*;

/**
 * Problem 7: Number of Islands
 * 
 * Given a 2D grid of '1's (land) and '0's (water), count islands.
 *
 * Approach: DFS/BFS from each unvisited '1', sink the island by marking visited as '0'.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n) worst case recursion stack
 *
 * Production Analogy: Connected component detection in network topology - finding
 * isolated clusters of servers. Also used in image segmentation (blob detection).
 */
public class Problem07_NumberOfIslands {

    public static int numIslands(char[][] grid) {
        int count = 0;
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] == '1') {
                    count++;
                    dfs(grid, i, j);
                }
        return count;
    }

    private static void dfs(char[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != '1') return;
        grid[i][j] = '0';
        dfs(grid, i+1, j); dfs(grid, i-1, j); dfs(grid, i, j+1); dfs(grid, i, j-1);
    }

    public static void main(String[] args) {
        char[][] g1 = {{'1','1','1','1','0'},{'1','1','0','1','0'},{'1','1','0','0','0'},{'0','0','0','0','0'}};
        System.out.println("Test 1: " + numIslands(g1)); // 1

        char[][] g2 = {{'1','1','0','0','0'},{'1','1','0','0','0'},{'0','0','1','0','0'},{'0','0','0','1','1'}};
        System.out.println("Test 2: " + numIslands(g2)); // 3

        char[][] g3 = {{'0'}};
        System.out.println("Test 3: " + numIslands(g3)); // 0

        char[][] g4 = {{'1'}};
        System.out.println("Test 4: " + numIslands(g4)); // 1
    }
}
