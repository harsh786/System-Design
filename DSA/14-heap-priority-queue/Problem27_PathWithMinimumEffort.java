import java.util.*;

/**
 * Problem 27: Path With Minimum Effort (LeetCode 1631)
 * 
 * Approach: Modified Dijkstra - min-heap by max absolute difference along path.
 * 
 * Time Complexity: O(M*N log(M*N))
 * Space Complexity: O(M*N)
 * 
 * Production Analogy: Network routing that minimizes maximum hop latency (bottleneck
 * path) rather than total latency.
 */
public class Problem27_PathWithMinimumEffort {
    
    public int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        int[][] effort = new int[m][n];
        for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
        effort[0][0] = 0;
        
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            int r = curr[0], c = curr[1], e = curr[2];
            if (r == m - 1 && c == n - 1) return e;
            if (e > effort[r][c]) continue;
            for (int[] d : dirs) {
                int nr = r + d[0], nc = c + d[1];
                if (nr < 0 || nr >= m || nc < 0 || nc >= n) continue;
                int newEffort = Math.max(e, Math.abs(heights[nr][nc] - heights[r][c]));
                if (newEffort < effort[nr][nc]) {
                    effort[nr][nc] = newEffort;
                    pq.offer(new int[]{nr, nc, newEffort});
                }
            }
        }
        return 0;
    }
    
    public static void main(String[] args) {
        Problem27_PathWithMinimumEffort sol = new Problem27_PathWithMinimumEffort();
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,3},{3,8,4},{5,3,5}})); // 1
    }
}
