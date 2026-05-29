import java.util.*;

/**
 * Problem: Longest Increasing Path in a Matrix
 *
 * Approach: Topological sort on implicit DAG (cell -> larger neighbors), BFS by levels
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Finding longest chain of escalating events in a monitoring grid.
 */
public class Problem22_LongestIncreasingPathInMatrix {

    public int longestIncreasingPath(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int[][] outDeg = new int[m][n];

        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                for (int[] d : dirs) {
                    int ni = i+d[0], nj = j+d[1];
                    if (ni>=0 && ni<m && nj>=0 && nj<n && matrix[ni][nj] > matrix[i][j])
                        outDeg[i][j]++;
                }

        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (outDeg[i][j] == 0) q.offer(new int[]{i,j});

        int levels = 0;
        while (!q.isEmpty()) {
            levels++;
            int size = q.size();
            for (int s = 0; s < size; s++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni>=0 && ni<m && nj>=0 && nj<n && matrix[ni][nj] < matrix[cell[0]][cell[1]])
                        if (--outDeg[ni][nj] == 0) q.offer(new int[]{ni,nj});
                }
            }
        }
        return levels;
    }

    public static void main(String[] args) {
        Problem22_LongestIncreasingPathInMatrix solver = new Problem22_LongestIncreasingPathInMatrix();
        System.out.println(solver.longestIncreasingPath(new int[][]{{9,9,4},{6,6,8},{2,1,1}})); // 4
    }
}
