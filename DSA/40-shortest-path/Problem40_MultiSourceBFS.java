import java.util.*;

/**
 * Problem: Multi-source BFS
 * Find minimum distance from any source to each cell.
 *
 * Approach: Start BFS from all sources simultaneously
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Computing nearest CDN POP distance for every client location.
 */
public class Problem40_MultiSourceBFS {

    public int[][] multiSourceBFS(int[][] grid, List<int[]> sources) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, -1);
        Queue<int[]> q = new LinkedList<>();
        for (int[] s : sources) { dist[s[0]][s[1]] = 0; q.offer(s); }

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&grid[nr][nc]==0&&dist[nr][nc]==-1) {
                    dist[nr][nc] = dist[cur[0]][cur[1]] + 1;
                    q.offer(new int[]{nr, nc});
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem40_MultiSourceBFS solver = new Problem40_MultiSourceBFS();
        int[][] grid = {{0,0,0},{0,1,0},{0,0,0}};
        List<int[]> sources = Arrays.asList(new int[]{0,0}, new int[]{2,2});
        int[][] res = solver.multiSourceBFS(grid, sources);
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
