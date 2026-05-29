/**
 * Problem 18: Matrix Block Sum (LeetCode 1314)
 * 
 * Pattern: 2D prefix sum + inclusion-exclusion for block queries
 * 
 * Time: O(m*n), Space: O(m*n)
 * 
 * Production Analogy: Image blurring (box filter) in image processing pipelines
 * using integral images (summed area tables).
 */
public class Problem18_MatrixBlockSum {

    public static int[][] matrixBlockSum(int[][] mat, int k) {
        int m = mat.length, n = mat[0].length;
        int[][] prefix = new int[m + 1][n + 1];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                prefix[i + 1][j + 1] = mat[i][j] + prefix[i][j + 1] + prefix[i + 1][j] - prefix[i][j];

        int[][] result = new int[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                int r1 = Math.max(0, i - k), c1 = Math.max(0, j - k);
                int r2 = Math.min(m - 1, i + k), c2 = Math.min(n - 1, j + k);
                result[i][j] = prefix[r2 + 1][c2 + 1] - prefix[r1][c2 + 1] - prefix[r2 + 1][c1] + prefix[r1][c1];
            }
        return result;
    }

    public static void main(String[] args) {
        int[][] r = matrixBlockSum(new int[][]{{1,2,3},{4,5,6},{7,8,9}}, 1);
        assert r[0][0] == 12 && r[1][1] == 45 && r[2][2] == 28;
        System.out.println("All tests passed!");
    }
}
