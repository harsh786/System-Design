import java.util.*;

/**
 * Problem: Shortest Path in Weighted Grid
 * Find shortest path from top-left to bottom-right in weighted grid.
 *
 * Approach: Dijkstra on grid treating cell values as edge weights
 *
 * Time Complexity: O(m*n*log(m*n))
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding minimum-cost path through a heterogeneous network.
 */
public class Problem50_ShortestPathInWeightedGrid {

    public int shortestPath(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = grid[0][0];

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, grid[0][0]});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int r = cur[0], c = cur[1], d = cur[2];
            if (r == m-1 && c == n-1) return d;
            if (d > dist[r][c]) continue;
            for (int[] dir : dirs) {
                int nr = r+dir[0], nc = c+dir[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n) {
                    int nd = d + grid[nr][nc];
                    if (nd < dist[nr][nc]) { dist[nr][nc] = nd; pq.offer(new int[]{nr, nc, nd}); }
                }
            }
        }
        return dist[m-1][n-1];
    }

    public static void main(String[] args) {
        Problem50_ShortestPathInWeightedGrid solver = new Problem50_ShortestPathInWeightedGrid();
        System.out.println(solver.shortestPath(new int[][]{{1,3,1},{1,5,1},{4,2,1}})); // 7
    }
}
