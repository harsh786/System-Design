import java.util.*;

/**
 * Problem 41: Minimum Falling Path Sum
 * 
 * Find minimum sum of a falling path (move down to adjacent column +-1).
 *
 * Approach: DP bottom-up. dp[i][j] = matrix[i][j] + min(dp[i-1][j-1], dp[i-1][j], dp[i-1][j+1])
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1) in-place
 *
 * Production Analogy: Finding minimum cost path through a multi-stage pipeline
 * where each stage can feed into adjacent stages only.
 */
public class Problem41_MinimumFallingPathSum {

    public static int minFallingPathSum(int[][] matrix) {
        int n = matrix.length;
        for (int i = 1; i < n; i++)
            for (int j = 0; j < n; j++) {
                int best = matrix[i-1][j];
                if (j > 0) best = Math.min(best, matrix[i-1][j-1]);
                if (j < n-1) best = Math.min(best, matrix[i-1][j+1]);
                matrix[i][j] += best;
            }
        int min = Integer.MAX_VALUE;
        for (int v : matrix[n-1]) min = Math.min(min, v);
        return min;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + minFallingPathSum(new int[][]{{2,1,3},{6,5,4},{7,8,9}})); // 13
        System.out.println("Test 2: " + minFallingPathSum(new int[][]{{-19,57},{-40,-5}})); // -59
    }
}
