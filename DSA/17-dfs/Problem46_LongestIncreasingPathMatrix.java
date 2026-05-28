/**
 * Problem: Longest Increasing Path in a Matrix (LeetCode 329)
 * Approach: DFS with memoization - each cell stores longest path starting from it
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Finding longest dependency chain in build systems for parallelization
 */
public class Problem46_LongestIncreasingPathMatrix {
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public int longestIncreasingPath(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        int[][] memo = new int[m][n];
        int max = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                max = Math.max(max, dfs(matrix, i, j, memo));
        return max;
    }

    private int dfs(int[][] matrix, int i, int j, int[][] memo) {
        if (memo[i][j] != 0) return memo[i][j];
        int max = 1;
        for (int[] d : dirs) {
            int ni = i+d[0], nj = j+d[1];
            if (ni >= 0 && ni < matrix.length && nj >= 0 && nj < matrix[0].length && matrix[ni][nj] > matrix[i][j])
                max = Math.max(max, 1 + dfs(matrix, ni, nj, memo));
        }
        memo[i][j] = max;
        return max;
    }

    public static void main(String[] args) {
        int[][] matrix = {{9,9,4},{6,6,8},{2,1,1}};
        System.out.println(new Problem46_LongestIncreasingPathMatrix().longestIncreasingPath(matrix)); // 4
    }
}
