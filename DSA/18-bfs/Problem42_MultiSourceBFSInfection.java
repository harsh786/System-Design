import java.util.*;

/**
 * Problem: Multi-source BFS Infection Spread
 * Approach: Multi-source BFS from all initially infected cells, spread each timestep
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Modeling cascading failure propagation from multiple initial failure points
 */
public class Problem42_MultiSourceBFSInfection {
    public int timeToInfectAll(int[][] grid) {
        int m = grid.length, n = grid[0].length, healthy = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 2) q.offer(new int[]{i, j});
                else if (grid[i][j] == 1) healthy++;
            }
        if (healthy == 0) return 0;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int time = 0;
        while (!q.isEmpty() && healthy > 0) {
            int size = q.size(); time++;
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] == 1) {
                        grid[ni][nj] = 2; healthy--; q.offer(new int[]{ni, nj});
                    }
                }
            }
        }
        return healthy == 0 ? time : -1;
    }

    public static void main(String[] args) {
        int[][] grid = {{1,1,1},{1,2,1},{1,1,1}};
        System.out.println(new Problem42_MultiSourceBFSInfection().timeToInfectAll(grid)); // 2
    }
}
