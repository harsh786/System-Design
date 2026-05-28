import java.util.*;

/**
 * Problem: As Far from Land as Possible (LeetCode 1162)
 * Approach: Multi-source BFS from all land cells, find max distance water cell
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Finding most isolated user from any server for worst-case latency analysis
 */
public class Problem18_AsFarFromLand {
    public int maxDistance(int[][] grid) {
        int n = grid.length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) q.offer(new int[]{i, j});
        if (q.size() == 0 || q.size() == n * n) return -1;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int dist = -1;
        while (!q.isEmpty()) {
            int size = q.size(); dist++;
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < n && nj >= 0 && nj < n && grid[ni][nj] == 0) {
                        grid[ni][nj] = 1; q.offer(new int[]{ni, nj});
                    }
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        int[][] grid = {{1,0,1},{0,0,0},{1,0,1}};
        System.out.println(new Problem18_AsFarFromLand().maxDistance(grid)); // 2
    }
}
