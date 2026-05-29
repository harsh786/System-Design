import java.util.*;

/**
 * Problem 40: Number of Distinct Islands
 * 
 * Count distinct island shapes (two islands are same if one can be translated to match other).
 *
 * Approach: DFS each island, record path signature (directions taken) relative to start.
 * Store signatures in a HashSet.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Deduplicating shapes in image recognition - like identifying
 * unique component layouts on a PCB regardless of position.
 */
public class Problem40_NumberOfDistinctIslands {

    public static int numDistinctIslands(int[][] grid) {
        Set<String> shapes = new HashSet<>();
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] == 1) {
                    StringBuilder sb = new StringBuilder();
                    dfs(grid, i, j, sb, 'S');
                    shapes.add(sb.toString());
                }
        return shapes.size();
    }

    private static void dfs(int[][] grid, int i, int j, StringBuilder sb, char dir) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return;
        grid[i][j] = 0;
        sb.append(dir);
        dfs(grid, i+1, j, sb, 'D'); dfs(grid, i-1, j, sb, 'U');
        dfs(grid, i, j+1, sb, 'R'); dfs(grid, i, j-1, sb, 'L');
        sb.append('B'); // backtrack marker
    }

    public static void main(String[] args) {
        int[][] g1 = {{1,1,0,0,0},{1,1,0,0,0},{0,0,0,1,1},{0,0,0,1,1}};
        System.out.println("Test 1: " + numDistinctIslands(g1)); // 1

        int[][] g2 = {{1,1,0,1,1},{1,0,0,0,0},{0,0,0,0,1},{1,1,0,1,1}};
        System.out.println("Test 2: " + numDistinctIslands(g2)); // 3
    }
}
