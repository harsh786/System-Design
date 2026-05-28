/**
 * Problem 40: Count Square Submatrices with All Ones
 * 
 * Same recurrence as Maximal Square but sum all dp values.
 * dp[i][j] = side of largest square with bottom-right at (i,j)
 * Answer = sum of all dp[i][j]
 * 
 * Time: O(m*n), Space: O(n)
 */
public class Problem40_CountSquareSubmatrices {

    public static int countSquares(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length, count = 0;
        int[] dp = new int[n];
        for (int i = 0; i < m; i++) {
            int[] newDp = new int[n];
            for (int j = 0; j < n; j++) {
                if (matrix[i][j] == 1) {
                    if (i == 0 || j == 0) newDp[j] = 1;
                    else newDp[j] = Math.min(dp[j], Math.min(newDp[j - 1], dp[j - 1])) + 1;
                    count += newDp[j];
                }
            }
            dp = newDp;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println("=== Count Square Submatrices ===");
        System.out.println(countSquares(new int[][]{
            {0,1,1,1},{1,1,1,1},{0,1,1,1}})); // 15
        System.out.println(countSquares(new int[][]{
            {1,0,1},{1,1,0},{1,1,0}})); // 7
    }
}
