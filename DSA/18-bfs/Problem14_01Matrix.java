import java.util.*;

/**
 * Problem: 01 Matrix (LeetCode 542)
 * Approach: Multi-source BFS from all 0 cells, expanding outward
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Computing latency to nearest cache node for all service instances
 */
public class Problem14_01Matrix {
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
            int[] cell = q.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n && dist[ni][nj] > dist[cell[0]][cell[1]] + 1) {
                    dist[ni][nj] = dist[cell[0]][cell[1]] + 1;
                    q.offer(new int[]{ni, nj});
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        int[][] mat = {{0,0,0},{0,1,0},{1,1,1}};
        int[][] res = new Problem14_01Matrix().updateMatrix(mat);
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
