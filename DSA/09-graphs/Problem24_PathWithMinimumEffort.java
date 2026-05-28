import java.util.*;

/**
 * Problem 24: Path With Minimum Effort (LeetCode 1631)
 * 
 * Approach: Dijkstra where edge weight = abs diff in heights. Minimize max edge on path.
 * Time: O(M*N*log(M*N)), Space: O(M*N)
 * 
 * Production Analogy: Finding network path minimizing worst-case latency spike between hops.
 */
public class Problem24_PathWithMinimumEffort {
    
    public int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        int[][] effort = new int[m][n];
        for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
        effort[0][0] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[2]-b[2]);
        pq.offer(new int[]{0, 0, 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] c = pq.poll();
            if (c[0] == m-1 && c[1] == n-1) return c[2];
            if (c[2] > effort[c[0]][c[1]]) continue;
            for (int[] d : dirs) {
                int ni = c[0]+d[0], nj = c[1]+d[1];
                if (ni>=0 && ni<m && nj>=0 && nj<n) {
                    int ne = Math.max(c[2], Math.abs(heights[ni][nj]-heights[c[0]][c[1]]));
                    if (ne < effort[ni][nj]) { effort[ni][nj] = ne; pq.offer(new int[]{ni, nj, ne}); }
                }
            }
        }
        return 0;
    }
    
    public static void main(String[] args) {
        Problem24_PathWithMinimumEffort sol = new Problem24_PathWithMinimumEffort();
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,3},{3,8,4},{5,3,5}})); // 1
        System.out.println(sol.minimumEffortPath(new int[][]{{1,2,1,1,1},{1,2,1,2,1},{1,2,1,2,1},{1,1,1,2,1}})); // 0
    }
}
