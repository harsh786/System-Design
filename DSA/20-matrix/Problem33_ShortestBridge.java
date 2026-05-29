import java.util.*;

/**
 * Problem 33: Shortest Bridge
 * 
 * Two islands in grid. Find minimum flips (0->1) to connect them.
 *
 * Approach: DFS to find first island and add all its cells to queue.
 * Then BFS outward from first island until reaching second island.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Finding minimum infrastructure (cables/links) needed to connect
 * two isolated network clusters.
 */
public class Problem33_ShortestBridge {

    public static int shortestBridge(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        Queue<int[]> queue = new LinkedList<>();
        boolean found = false;
        // DFS to find first island
        for (int i = 0; i < m && !found; i++)
            for (int j = 0; j < n && !found; j++)
                if (grid[i][j] == 1) {
                    dfs(grid, i, j, queue);
                    found = true;
                }
        // BFS to reach second island
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!queue.isEmpty()) {
            int size = queue.size();
            while (size-- > 0) {
                int[] cell = queue.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n) {
                        if (grid[ni][nj] == 1) return steps;
                        if (grid[ni][nj] == 0) {
                            grid[ni][nj] = 2;
                            queue.offer(new int[]{ni, nj});
                        }
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    private static void dfs(int[][] grid, int i, int j, Queue<int[]> queue) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return;
        grid[i][j] = 2;
        queue.offer(new int[]{i, j});
        dfs(grid, i+1, j, queue); dfs(grid, i-1, j, queue);
        dfs(grid, i, j+1, queue); dfs(grid, i, j-1, queue);
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + shortestBridge(new int[][]{{0,1},{1,0}})); // 1
        System.out.println("Test 2: " + shortestBridge(new int[][]{{0,1,0},{0,0,0},{0,0,1}})); // 2
    }
}
