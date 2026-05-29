import java.util.*;

/**
 * Problem 34: Making A Large Island
 * 
 * Change at most one 0 to 1. Find largest island possible.
 *
 * Approach: 
 * 1. Label each island with unique id and compute area.
 * 2. For each 0-cell, check adjacent island ids and sum their areas + 1.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Merging two data center regions by adding one link - finding
 * which single connection would create the largest unified cluster.
 */
public class Problem34_MakingALargeIsland {

    public static int largestIsland(int[][] grid) {
        int n = grid.length, id = 2, maxArea = 0;
        Map<Integer, Integer> areaMap = new HashMap<>();
        // Label islands
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) {
                    int area = dfs(grid, i, j, id);
                    areaMap.put(id, area);
                    maxArea = Math.max(maxArea, area);
                    id++;
                }
        // Try flipping each 0
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 0) {
                    Set<Integer> seen = new HashSet<>();
                    int area = 1;
                    for (int[] d : dirs) {
                        int ni = i+d[0], nj = j+d[1];
                        if (ni >= 0 && ni < n && nj >= 0 && nj < n && grid[ni][nj] > 1 && seen.add(grid[ni][nj]))
                            area += areaMap.get(grid[ni][nj]);
                    }
                    maxArea = Math.max(maxArea, area);
                }
        return maxArea;
    }

    private static int dfs(int[][] grid, int i, int j, int id) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return 0;
        grid[i][j] = id;
        return 1 + dfs(grid, i+1, j, id) + dfs(grid, i-1, j, id) + dfs(grid, i, j+1, id) + dfs(grid, i, j-1, id);
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + largestIsland(new int[][]{{1,0},{0,1}})); // 3
        System.out.println("Test 2: " + largestIsland(new int[][]{{1,1},{1,0}})); // 4
        System.out.println("Test 3: " + largestIsland(new int[][]{{1,1},{1,1}})); // 4
    }
}
