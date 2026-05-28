/**
 * Problem 38: Maximal Square
 * 
 * Find largest square containing only 1s in a binary matrix.
 * 
 * State: dp[i][j] = side length of largest square with bottom-right at (i,j)
 * Recurrence: dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
 * 
 * Time: O(m*n), Space: O(n)
 */
public class Problem38_MaximalSquare {

    public static int maximalSquare(char[][] matrix) {
        int m = matrix.length, n = matrix[0].length, maxSide = 0;
        int[] dp = new int[n + 1];
        int prev = 0;
        for (int i = 0; i < m; i++) {
            for (int j = 1; j <= n; j++) {
                int tmp = dp[j];
                if (matrix[i][j - 1] == '1') {
                    dp[j] = Math.min(dp[j], Math.min(dp[j - 1], prev)) + 1;
                    maxSide = Math.max(maxSide, dp[j]);
                } else {
                    dp[j] = 0;
                }
                prev = tmp;
            }
            prev = 0;
        }
        return maxSide * maxSide;
    }

    public static void main(String[] args) {
        System.out.println("=== Maximal Square ===");
        char[][] matrix = {
            {'1','0','1','0','0'},
            {'1','0','1','1','1'},
            {'1','1','1','1','1'},
            {'1','0','0','1','0'}
        };
        System.out.println(maximalSquare(matrix)); // 4
    }
}
