import java.util.*;

/**
 * Problem 30: Matrix Block Sum
 * 
 * For each cell (i,j), compute sum of all elements in submatrix from
 * (i-k, j-k) to (i+k, j+k).
 *
 * Approach: Build 2D prefix sum, then query each block in O(1).
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Computing regional aggregates in spatial data - like average
 * temperature in a k-radius around each sensor in a grid of weather stations.
 */
public class Problem30_MatrixBlockSum {

    public static int[][] matrixBlockSum(int[][] mat, int k) {
        int m = mat.length, n = mat[0].length;
        int[][] prefix = new int[m+1][n+1];
        for (int i = 1; i <= m; i++)
            for (int j = 1; j <= n; j++)
                prefix[i][j] = mat[i-1][j-1] + prefix[i-1][j] + prefix[i][j-1] - prefix[i-1][j-1];

        int[][] result = new int[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                int r1 = Math.max(0, i-k), c1 = Math.max(0, j-k);
                int r2 = Math.min(m-1, i+k), c2 = Math.min(n-1, j+k);
                result[i][j] = prefix[r2+1][c2+1] - prefix[r1][c2+1] - prefix[r2+1][c1] + prefix[r1][c1];
            }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(matrixBlockSum(new int[][]{{1,2,3},{4,5,6},{7,8,9}}, 1)));
        // [[12,21,16],[27,45,33],[24,39,28]]
        System.out.println("Test 2: " + Arrays.deepToString(matrixBlockSum(new int[][]{{1,2,3},{4,5,6},{7,8,9}}, 2)));
    }
}
