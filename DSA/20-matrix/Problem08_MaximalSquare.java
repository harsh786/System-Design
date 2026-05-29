import java.util.*;

/**
 * Problem 8: Maximal Square
 * 
 * Find the largest square containing only 1's and return its area.
 *
 * Approach: DP where dp[i][j] = side length of largest square with bottom-right at (i,j).
 * dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1 if matrix[i][j] == '1'
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(n) with space optimization
 *
 * Production Analogy: Finding the largest contiguous block of available slots in a
 * memory allocator grid, or the largest clear area on a warehouse floor plan.
 */
public class Problem08_MaximalSquare {

    public static int maximalSquare(char[][] matrix) {
        int m = matrix.length, n = matrix[0].length, maxSide = 0;
        int[][] dp = new int[m + 1][n + 1];
        for (int i = 1; i <= m; i++)
            for (int j = 1; j <= n; j++)
                if (matrix[i-1][j-1] == '1') {
                    dp[i][j] = Math.min(Math.min(dp[i-1][j], dp[i][j-1]), dp[i-1][j-1]) + 1;
                    maxSide = Math.max(maxSide, dp[i][j]);
                }
        return maxSide * maxSide;
    }

    public static void main(String[] args) {
        char[][] m1 = {{'1','0','1','0','0'},{'1','0','1','1','1'},{'1','1','1','1','1'},{'1','0','0','1','0'}};
        System.out.println("Test 1: " + maximalSquare(m1)); // 4

        char[][] m2 = {{'0','1'},{'1','0'}};
        System.out.println("Test 2: " + maximalSquare(m2)); // 1

        char[][] m3 = {{'0'}};
        System.out.println("Test 3: " + maximalSquare(m3)); // 0

        char[][] m4 = {{'1','1'},{'1','1'}};
        System.out.println("Test 4: " + maximalSquare(m4)); // 4
    }
}
