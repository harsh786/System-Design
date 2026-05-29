import java.util.*;

/**
 * Problem 49: Transpose Matrix
 * 
 * Return transpose of matrix (swap rows and columns).
 *
 * Approach: Create new m x n -> n x m matrix where result[j][i] = matrix[i][j].
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Converting row-major to column-major storage format in databases.
 * Columnar databases (like Parquet) transpose row data for better compression and
 * analytical query performance.
 */
public class Problem49_TransposeMatrix {

    public static int[][] transpose(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        int[][] result = new int[n][m];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                result[j][i] = matrix[i][j];
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(transpose(new int[][]{{1,2,3},{4,5,6},{7,8,9}})));
        // [[1,4,7],[2,5,8],[3,6,9]]
        System.out.println("Test 2: " + Arrays.deepToString(transpose(new int[][]{{1,2,3},{4,5,6}})));
        // [[1,4],[2,5],[3,6]]
    }
}
