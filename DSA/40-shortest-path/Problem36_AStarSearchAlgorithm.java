import java.util.*;

/**
 * Problem: A* Search Algorithm
 * Shortest path with heuristic guidance (Manhattan distance on grid).
 *
 * Approach: Priority queue ordered by f(n) = g(n) + h(n)
 *
 * Time Complexity: O(E log V) with good heuristic
 * Space Complexity: O(V)
 *
 * Production Analogy: Intelligent routing with geographic hints (like Google Maps).
 */
public class Problem36_AStarSearchAlgorithm {

    public int astar(int[][] grid, int[] start, int[] end) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[start[0]][start[1]] = 0;

        // PQ: {row, col, f=g+h}
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{start[0], start[1], heuristic(start, end)});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int r = cur[0], c = cur[1];
            if (r == end[0] && c == end[1]) return dist[r][c];
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&grid[nr][nc]==0) {
                    int g = dist[r][c] + 1;
                    if (g < dist[nr][nc]) {
                        dist[nr][nc] = g;
                        pq.offer(new int[]{nr, nc, g + heuristic(new int[]{nr,nc}, end)});
                    }
                }
            }
        }
        return -1;
    }

    private int heuristic(int[] a, int[] b) {
        return Math.abs(a[0]-b[0]) + Math.abs(a[1]-b[1]);
    }

    public static void main(String[] args) {
        Problem36_AStarSearchAlgorithm solver = new Problem36_AStarSearchAlgorithm();
        int[][] grid = {{0,0,0,0},{0,1,1,0},{0,0,0,0},{0,1,0,0}};
        System.out.println(solver.astar(grid, new int[]{0,0}, new int[]{3,3})); // 6
    }
}
