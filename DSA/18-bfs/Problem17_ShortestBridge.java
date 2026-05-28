import java.util.*;

/**
 * Problem: Shortest Bridge (LeetCode 934)
 * Approach: DFS to find first island, then BFS to expand until reaching second island
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Minimum network links to connect two isolated data centers
 */
public class Problem17_ShortestBridge {
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public int shortestBridge(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        Queue<int[]> q = new LinkedList<>();
        boolean found = false;
        for (int i = 0; i < m && !found; i++)
            for (int j = 0; j < n && !found; j++)
                if (grid[i][j] == 1) { dfs(grid, i, j, q); found = true; }
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] != 2) {
                        if (grid[ni][nj] == 1) return steps;
                        grid[ni][nj] = 2; q.offer(new int[]{ni, nj});
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    private void dfs(int[][] grid, int i, int j, Queue<int[]> q) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 1) return;
        grid[i][j] = 2; q.offer(new int[]{i, j});
        for (int[] d : dirs) dfs(grid, i+d[0], j+d[1], q);
    }

    public static void main(String[] args) {
        int[][] grid = {{0,1,0},{0,0,0},{0,0,1}};
        System.out.println(new Problem17_ShortestBridge().shortestBridge(grid)); // 2
    }
}
