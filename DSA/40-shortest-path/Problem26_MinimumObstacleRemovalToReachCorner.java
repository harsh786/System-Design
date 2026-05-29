import java.util.*;

/**
 * Problem: Minimum Obstacle Removal to Reach Corner
 *
 * Approach: 0-1 BFS - empty cell = 0 cost, obstacle = 1 cost
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Minimum firewall rules to change for establishing a network path.
 */
public class Problem26_MinimumObstacleRemovalToReachCorner {

    public int minimumObstacles(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = 0;
        Deque<int[]> dq = new ArrayDeque<>();
        dq.offer(new int[]{0, 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!dq.isEmpty()) {
            int[] cur = dq.poll();
            int r = cur[0], c = cur[1];
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n) {
                    int cost = dist[r][c] + grid[nr][nc];
                    if (cost < dist[nr][nc]) {
                        dist[nr][nc] = cost;
                        if (grid[nr][nc] == 0) dq.offerFirst(new int[]{nr,nc});
                        else dq.offerLast(new int[]{nr,nc});
                    }
                }
            }
        }
        return dist[m-1][n-1];
    }

    public static void main(String[] args) {
        Problem26_MinimumObstacleRemovalToReachCorner solver = new Problem26_MinimumObstacleRemovalToReachCorner();
        System.out.println(solver.minimumObstacles(new int[][]{{0,1,1},{1,1,0},{1,1,0}})); // 2
    }
}
