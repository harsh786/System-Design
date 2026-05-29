package numbertheory;

/**
 * Problem 14: Perfect Squares (LeetCode 279)
 * 
 * Approach: BFS or DP. By Lagrange's four-square theorem, answer is 1-4.
 * Using DP: dp[i] = min(dp[i-j*j] + 1) for all valid j.
 * 
 * Time Complexity: O(n * sqrt(n))
 * Space Complexity: O(n)
 */
public class Problem14_PerfectSquares {
    
    public int numSquares(int n) {
        int[] dp = new int[n + 1];
        java.util.Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int i = 1; i <= n; i++)
            for (int j = 1; j * j <= i; j++)
                dp[i] = Math.min(dp[i], dp[i - j * j] + 1);
        return dp[n];
    }
    
    public static void main(String[] args) {
        Problem14_PerfectSquares sol = new Problem14_PerfectSquares();
        System.out.println(sol.numSquares(12)); // 3
        System.out.println(sol.numSquares(13)); // 2
    }
}
