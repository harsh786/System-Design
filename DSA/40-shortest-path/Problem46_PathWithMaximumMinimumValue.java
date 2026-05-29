import java.util.*;

/**
 * Problem: Path With Maximum Minimum Value
 * Find path from (0,0) to (m-1,n-1) maximizing the minimum value along path.
 *
 * Approach: Modified Dijkstra with max-heap tracking minimum value on path
 *
 * Time Complexity: O(m*n*log(m*n))
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding path maximizing minimum bandwidth (bottleneck path).
 */
public class Problem46_PathWithMaximumMinimumValue {

    public int maximumMinimumPath(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] maxMin = new int[m][n];
        for (int[] row : maxMin) Arrays.fill(row, -1);
        maxMin[0][0] = grid[0][0];

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[2] - a[2]);
        pq.offer(new int[]{0, 0, grid[0][0]});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int r = cur[0], c = cur[1], val = cur[2];
            if (r == m-1 && c == n-1) return val;
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n) {
                    int nv = Math.min(val, grid[nr][nc]);
                    if (nv > maxMin[nr][nc]) { maxMin[nr][nc] = nv; pq.offer(new int[]{nr, nc, nv}); }
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem46_PathWithMaximumMinimumValue solver = new Problem46_PathWithMaximumMinimumValue();
        System.out.println(solver.maximumMinimumPath(new int[][]{{5,4,5},{1,2,6},{7,4,6}})); // 4
    }
}
