import java.util.*;

/**
 * Problem: Rotting Oranges (LeetCode 994)
 * Approach: Multi-source BFS from all rotten oranges simultaneously
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Modeling infection/failure propagation in distributed systems
 */
public class Problem02_RottingOranges {
    public int orangesRotting(int[][] grid) {
        int m = grid.length, n = grid[0].length, fresh = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 2) q.offer(new int[]{i, j});
                else if (grid[i][j] == 1) fresh++;
            }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int minutes = 0;
        while (!q.isEmpty() && fresh > 0) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] == 1) {
                        grid[ni][nj] = 2; fresh--; q.offer(new int[]{ni, nj});
                    }
                }
            }
            minutes++;
        }
        return fresh == 0 ? minutes : -1;
    }

    public static void main(String[] args) {
        int[][] grid = {{2,1,1},{1,1,0},{0,1,1}};
        System.out.println(new Problem02_RottingOranges().orangesRotting(grid)); // 4
    }
}
