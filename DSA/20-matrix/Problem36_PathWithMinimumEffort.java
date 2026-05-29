import java.util.*;

/**
 * Problem 36: Path With Minimum Effort
 * 
 * Find path from top-left to bottom-right minimizing maximum absolute difference
 * between consecutive cells.
 *
 * Approach: Dijkstra with priority queue. Cost = max effort along path so far.
 *
 * Time Complexity: O(m * n * log(m*n))
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Network routing minimizing worst-case link quality degradation.
 * Finding a path where the weakest link is as strong as possible.
 */
public class Problem36_PathWithMinimumEffort {

    public static int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        int[][] effort = new int[m][n];
        for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
        effort[0][0] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int i = cur[0], j = cur[1], e = cur[2];
            if (i == m-1 && j == n-1) return e;
            if (e > effort[i][j]) continue;
            for (int[] d : dirs) {
                int ni = i+d[0], nj = j+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n) {
                    int ne = Math.max(e, Math.abs(heights[ni][nj] - heights[i][j]));
                    if (ne < effort[ni][nj]) {
                        effort[ni][nj] = ne;
                        pq.offer(new int[]{ni, nj, ne});
                    }
                }
            }
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
        System.out.println("Test 2: " + minimumEffortPath(new int[][]{{1,2,3},{3,8,4},{5,3,5}})); // 1
        System.out.println("Test 3: " + minimumEffortPath(new int[][]{{1,2,1,1,1},{1,2,1,2,1},{1,2,1,2,1},{1,2,1,2,1},{1,1,1,2,1}})); // 0
    }
}
