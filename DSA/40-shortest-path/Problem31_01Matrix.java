import java.util.*;

/**
 * Problem: 01 Matrix
 * Find distance of nearest 0 for each cell.
 *
 * Approach: Multi-source BFS from all 0-cells
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Computing nearest cache/CDN distance for each client.
 */
public class Problem31_01Matrix {

    public int[][] updateMatrix(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        int[][] dist = new int[m][n];
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (mat[i][j] == 0) q.offer(new int[]{i, j});
                else dist[i][j] = Integer.MAX_VALUE;
            }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&dist[nr][nc]>dist[cur[0]][cur[1]]+1) {
                    dist[nr][nc] = dist[cur[0]][cur[1]] + 1;
                    q.offer(new int[]{nr, nc});
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem31_01Matrix solver = new Problem31_01Matrix();
        int[][] res = solver.updateMatrix(new int[][]{{0,0,0},{0,1,0},{1,1,1}});
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
