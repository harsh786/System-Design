import java.util.*;

/**
 * Problem: Minimum Cost to Make at Least One Valid Path
 * Grid with arrows, change direction costs 1. Find min cost path to bottom-right.
 *
 * Approach: 0-1 BFS - following arrow = 0 cost, changing = 1 cost
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Minimum config changes to route traffic from source to destination.
 */
public class Problem14_MinimumCostToMakeAtLeastOneValidPath {

    public int minCost(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}}; // right, left, down, up (1-indexed in grid)
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = 0;

        Deque<int[]> dq = new ArrayDeque<>();
        dq.offer(new int[]{0, 0});

        while (!dq.isEmpty()) {
            int[] cur = dq.poll();
            int r = cur[0], c = cur[1];
            for (int i = 0; i < 4; i++) {
                int nr = r + dirs[i][0], nc = c + dirs[i][1];
                int cost = (grid[r][c] - 1 == i) ? 0 : 1;
                if (nr>=0 && nr<m && nc>=0 && nc<n && dist[r][c]+cost < dist[nr][nc]) {
                    dist[nr][nc] = dist[r][c] + cost;
                    if (cost == 0) dq.offerFirst(new int[]{nr, nc});
                    else dq.offerLast(new int[]{nr, nc});
                }
            }
        }
        return dist[m-1][n-1];
    }

    public static void main(String[] args) {
        Problem14_MinimumCostToMakeAtLeastOneValidPath solver = new Problem14_MinimumCostToMakeAtLeastOneValidPath();
        System.out.println(solver.minCost(new int[][]{{1,1,1,1},{2,2,2,2},{1,1,1,1},{2,2,2,2}})); // 3
    }
}
