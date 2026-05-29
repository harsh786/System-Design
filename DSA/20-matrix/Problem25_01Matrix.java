import java.util.*;

/**
 * Problem 25: 01 Matrix
 * 
 * Find distance of nearest 0 for each cell.
 *
 * Approach: Multi-source BFS from all 0-cells simultaneously.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Computing distance to nearest service point in a grid - like
 * nearest hospital, fire station, or nearest available server in a data center floor plan.
 */
public class Problem25_01Matrix {

    public static int[][] updateMatrix(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        int[][] dist = new int[m][n];
        Queue<int[]> queue = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (mat[i][j] == 0) queue.offer(new int[]{i, j});
                else dist[i][j] = Integer.MAX_VALUE;
            }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!queue.isEmpty()) {
            int[] cell = queue.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n && dist[ni][nj] > dist[cell[0]][cell[1]] + 1) {
                    dist[ni][nj] = dist[cell[0]][cell[1]] + 1;
                    queue.offer(new int[]{ni, nj});
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(updateMatrix(new int[][]{{0,0,0},{0,1,0},{0,0,0}})));
        System.out.println("Test 2: " + Arrays.deepToString(updateMatrix(new int[][]{{0,0,0},{0,1,0},{1,1,1}})));
    }
}
