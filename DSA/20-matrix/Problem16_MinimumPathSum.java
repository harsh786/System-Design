import java.util.*;

/**
 * Problem 16: Minimum Path Sum
 * 
 * Find path from top-left to bottom-right with minimum sum (move right or down only).
 *
 * Approach: DP in-place. grid[i][j] += min(grid[i-1][j], grid[i][j-1])
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1) in-place
 *
 * Production Analogy: Minimum cost routing in a grid network where each hop has a cost.
 * Used in logistics for cheapest delivery path in a warehouse grid.
 */
public class Problem16_MinimumPathSum {

    public static int minPathSum(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        for (int i = 1; i < m; i++) grid[i][0] += grid[i-1][0];
        for (int j = 1; j < n; j++) grid[0][j] += grid[0][j-1];
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                grid[i][j] += Math.min(grid[i-1][j], grid[i][j-1]);
        return grid[m-1][n-1];
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + minPathSum(new int[][]{{1,3,1},{1,5,1},{4,2,1}})); // 7
        System.out.println("Test 2: " + minPathSum(new int[][]{{1,2,3},{4,5,6}})); // 12
    }
}
