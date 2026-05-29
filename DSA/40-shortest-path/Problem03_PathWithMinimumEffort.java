import java.util.*;

/**
 * Problem: Path With Minimum Effort
 * Find path from top-left to bottom-right minimizing max absolute difference.
 *
 * Approach: Dijkstra where edge weight = abs diff between cells
 *
 * Time Complexity: O(m*n*log(m*n))
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding network path minimizing worst-case link degradation.
 */
public class Problem03_PathWithMinimumEffort {

    public int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        int[][] effort = new int[m][n];
        for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
        effort[0][0] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int r = cur[0], c = cur[1], e = cur[2];
            if (r == m-1 && c == n-1) return e;
            if (e > effort[r][c]) continue;
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr>=0 && nr<m && nc>=0 && nc<n) {
                    int ne = Math.max(e, Math.abs(heights[nr][nc] - heights[r][c]));
                    if (ne < effort[nr][nc]) { effort[nr][nc] = ne; pq.offer(new int[]{nr, nc, ne}); }
                }
            }
        }
        return 0;
    }

    public static void main(String[] args) {
        Problem03_PathWithMinimumEffort solver = new Problem03_PathWithMinimumEffort();
        System.out.println(solver.minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
    }
}
