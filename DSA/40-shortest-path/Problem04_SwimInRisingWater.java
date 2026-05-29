import java.util.*;

/**
 * Problem: Swim in Rising Water
 * Find minimum time to swim from (0,0) to (n-1,n-1).
 *
 * Approach: Dijkstra/binary search - minimize max elevation along path
 *
 * Time Complexity: O(n^2 log n)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Finding when a network path becomes fully available given staged rollouts.
 */
public class Problem04_SwimInRisingWater {

    public int swimInWater(int[][] grid) {
        int n = grid.length;
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = grid[0][0];

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, grid[0][0]});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int r = cur[0], c = cur[1], t = cur[2];
            if (r == n-1 && c == n-1) return t;
            if (t > dist[r][c]) continue;
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr>=0 && nr<n && nc>=0 && nc<n) {
                    int nt = Math.max(t, grid[nr][nc]);
                    if (nt < dist[nr][nc]) { dist[nr][nc] = nt; pq.offer(new int[]{nr, nc, nt}); }
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem04_SwimInRisingWater solver = new Problem04_SwimInRisingWater();
        System.out.println(solver.swimInWater(new int[][]{{0,2},{1,3}})); // 3
    }
}
