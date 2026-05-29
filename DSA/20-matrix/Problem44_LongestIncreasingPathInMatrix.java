import java.util.*;

/**
 * Problem 44: Longest Increasing Path in a Matrix
 * 
 * Find length of longest strictly increasing path.
 *
 * Approach: DFS with memoization. For each cell, try all 4 directions where neighbor > current.
 *
 * Time Complexity: O(m * n) - each cell computed once
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Finding the longest dependency chain in a build system DAG
 * laid out on a grid - determines critical path for parallel build scheduling.
 */
public class Problem44_LongestIncreasingPathInMatrix {

    public static int longestIncreasingPath(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length, max = 0;
        int[][] memo = new int[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                max = Math.max(max, dfs(matrix, memo, i, j));
        return max;
    }

    private static int dfs(int[][] matrix, int[][] memo, int i, int j) {
        if (memo[i][j] != 0) return memo[i][j];
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int best = 1;
        for (int[] d : dirs) {
            int ni = i+d[0], nj = j+d[1];
            if (ni >= 0 && ni < matrix.length && nj >= 0 && nj < matrix[0].length && matrix[ni][nj] > matrix[i][j])
                best = Math.max(best, 1 + dfs(matrix, memo, ni, nj));
        }
        return memo[i][j] = best;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + longestIncreasingPath(new int[][]{{9,9,4},{6,6,8},{2,1,1}})); // 4
        System.out.println("Test 2: " + longestIncreasingPath(new int[][]{{3,4,5},{3,2,6},{2,2,1}})); // 4
        System.out.println("Test 3: " + longestIncreasingPath(new int[][]{{1}})); // 1
    }
}
