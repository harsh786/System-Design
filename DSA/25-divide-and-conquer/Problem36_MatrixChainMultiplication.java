/**
 * Problem 36: Matrix Chain Multiplication
 * 
 * D&C Approach:
 * - DIVIDE: For matrices A[i..j], try every split point k between i and j
 * - CONQUER: Recursively solve A[i..k] and A[k+1..j]
 * - COMBINE: Cost = cost(left) + cost(right) + cost(multiplying the two results)
 * 
 * Time: O(n^3) with memoization (Catalan number without), Space: O(n^2)
 * 
 * Production Analogy:
 * - SQL query optimizer choosing join order
 * - Compiler optimization for expression evaluation order
 * - Minimizing data transfer in distributed matrix operations (ML training)
 */
public class Problem36_MatrixChainMultiplication {

    // Bottom-up DP
    public static int matrixChainOrder(int[] dims) {
        int n = dims.length - 1; // n matrices
        int[][] dp = new int[n][n];
        
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                dp[i][j] = Integer.MAX_VALUE;
                for (int k = i; k < j; k++) {
                    int cost = dp[i][k] + dp[k + 1][j] + dims[i] * dims[k + 1] * dims[j + 1];
                    dp[i][j] = Math.min(dp[i][j], cost);
                }
            }
        }
        return dp[0][n - 1];
    }

    // Recursive D&C with memoization
    public static int matrixChainRecursive(int[] dims) {
        int n = dims.length - 1;
        int[][] memo = new int[n][n];
        return solve(dims, memo, 0, n - 1);
    }

    private static int solve(int[] dims, int[][] memo, int i, int j) {
        if (i == j) return 0;
        if (memo[i][j] != 0) return memo[i][j];
        memo[i][j] = Integer.MAX_VALUE;
        for (int k = i; k < j; k++) {
            int cost = solve(dims, memo, i, k) + solve(dims, memo, k + 1, j)
                     + dims[i] * dims[k + 1] * dims[j + 1];
            memo[i][j] = Math.min(memo[i][j], cost);
        }
        return memo[i][j];
    }

    public static void main(String[] args) {
        // Matrices: 40x20, 20x30, 30x10, 10x30
        System.out.println(matrixChainOrder(new int[]{40, 20, 30, 10, 30})); // 26000
        System.out.println(matrixChainRecursive(new int[]{40, 20, 30, 10, 30})); // 26000
        System.out.println(matrixChainOrder(new int[]{10, 20, 30})); // 6000
        System.out.println(matrixChainOrder(new int[]{10, 20, 30, 40, 30})); // 30000
    }
}
