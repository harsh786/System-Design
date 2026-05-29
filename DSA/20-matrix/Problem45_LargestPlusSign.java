import java.util.*;

/**
 * Problem 45: Largest Plus Sign
 * 
 * Find largest plus sign of 1s in an n x n grid with some cells set to 0.
 *
 * Approach: For each cell, compute min arm length in all 4 directions.
 * Precompute consecutive 1s in each direction.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Finding the largest intersection point in a road grid
 * with maximum visibility/reach in all four directions - useful for optimal
 * placement of a communication tower.
 */
public class Problem45_LargestPlusSign {

    public static int orderOfLargestPlusSign(int n, int[][] mines) {
        int[][] grid = new int[n][n];
        for (int[] row : grid) Arrays.fill(row, 1);
        for (int[] mine : mines) grid[mine[0]][mine[1]] = 0;

        int[][] dp = new int[n][n]; // min arm in all 4 directions
        for (int[] row : dp) Arrays.fill(row, n);

        for (int i = 0; i < n; i++) {
            int left = 0, right = 0, up = 0, down = 0;
            for (int j = 0; j < n; j++) {
                left = grid[i][j] == 0 ? 0 : left + 1;
                dp[i][j] = Math.min(dp[i][j], left);
            }
            for (int j = n-1; j >= 0; j--) {
                right = grid[i][j] == 0 ? 0 : right + 1;
                dp[i][j] = Math.min(dp[i][j], right);
            }
            for (int j = 0; j < n; j++) {
                up = grid[j][i] == 0 ? 0 : up + 1;
                dp[j][i] = Math.min(dp[j][i], up);
            }
            for (int j = n-1; j >= 0; j--) {
                down = grid[j][i] == 0 ? 0 : down + 1;
                dp[j][i] = Math.min(dp[j][i], down);
            }
        }

        int max = 0;
        for (int[] row : dp) for (int v : row) max = Math.max(max, v);
        return max;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + orderOfLargestPlusSign(5, new int[][]{{4,2}})); // 2
        System.out.println("Test 2: " + orderOfLargestPlusSign(1, new int[][]{{0,0}})); // 0
        System.out.println("Test 3: " + orderOfLargestPlusSign(2, new int[][]{})); // 1
    }
}
