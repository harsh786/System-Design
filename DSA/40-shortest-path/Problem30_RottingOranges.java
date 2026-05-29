import java.util.*;

/**
 * Problem: Rotting Oranges (Multi-source BFS)
 *
 * Approach: Multi-source BFS from all rotten oranges simultaneously
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Simulating failure propagation across connected services.
 */
public class Problem30_RottingOranges {

    public int orangesRotting(int[][] grid) {
        int m = grid.length, n = grid[0].length, fresh = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 2) q.offer(new int[]{i, j});
                else if (grid[i][j] == 1) fresh++;
            }
        if (fresh == 0) return 0;

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int minutes = 0;
        while (!q.isEmpty()) {
            int size = q.size(); boolean rotted = false;
            for (int i = 0; i < size; i++) {
                int[] cur = q.poll();
                for (int[] d : dirs) {
                    int nr = cur[0]+d[0], nc = cur[1]+d[1];
                    if (nr>=0&&nr<m&&nc>=0&&nc<n&&grid[nr][nc]==1) {
                        grid[nr][nc] = 2; fresh--; rotted = true; q.offer(new int[]{nr, nc});
                    }
                }
            }
            if (rotted) minutes++;
        }
        return fresh == 0 ? minutes : -1;
    }

    public static void main(String[] args) {
        Problem30_RottingOranges solver = new Problem30_RottingOranges();
        System.out.println(solver.orangesRotting(new int[][]{{2,1,1},{1,1,0},{0,1,1}})); // 4
    }
}
