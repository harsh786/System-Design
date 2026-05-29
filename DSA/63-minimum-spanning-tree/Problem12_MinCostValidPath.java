import java.util.*;

public class Problem12_MinCostValidPath {
    /* Minimum cost to make at least one valid path in grid - 0-1 BFS */
    public int minCost(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int[][] dist = new int[m][n];
        for (int[] r : dist) Arrays.fill(r, Integer.MAX_VALUE);
        dist[0][0] = 0;
        Deque<int[]> dq = new ArrayDeque<>();
        dq.offer(new int[]{0, 0});
        while (!dq.isEmpty()) {
            int[] cur = dq.poll();
            int r = cur[0], c = cur[1];
            for (int d = 0; d < 4; d++) {
                int nr = r + dirs[d][0], nc = c + dirs[d][1];
                if (nr < 0 || nr >= m || nc < 0 || nc >= n) continue;
                int cost = dist[r][c] + (grid[r][c] == d + 1 ? 0 : 1);
                if (cost < dist[nr][nc]) { dist[nr][nc] = cost; if (grid[r][c] == d+1) dq.offerFirst(new int[]{nr,nc}); else dq.offerLast(new int[]{nr,nc}); }
            }
        }
        return dist[m-1][n-1];
    }

    public static void main(String[] args) {
        Problem12_MinCostValidPath sol = new Problem12_MinCostValidPath();
        System.out.println(sol.minCost(new int[][]{{1,1,1,1},{2,2,2,2},{1,1,1,1},{2,2,2,2}})); // 3
    }
}
