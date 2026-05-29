/**
 * Problem: Count Square Submatrices with All Ones (LeetCode 1277)
 * Approach: DP - dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
 * Complexity: O(m*n) time, O(1) space (in-place)
 * Production Analogy: Contiguous region detection in image processing
 */
public class Problem34_CountSquareSubmatrices {
    public int countSquares(int[][] matrix) {
        int count = 0;
        for (int i = 0; i < matrix.length; i++) {
            for (int j = 0; j < matrix[0].length; j++) {
                if (matrix[i][j] == 1 && i > 0 && j > 0)
                    matrix[i][j] = Math.min(Math.min(matrix[i-1][j], matrix[i][j-1]), matrix[i-1][j-1]) + 1;
                count += matrix[i][j];
            }
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem34_CountSquareSubmatrices().countSquares(
            new int[][]{{0,1,1,1},{1,1,1,1},{0,1,1,1}})); // 15
    }
}
