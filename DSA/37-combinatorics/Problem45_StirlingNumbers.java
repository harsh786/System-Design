public class Problem45_StirlingNumbers {
    // Stirling numbers of the second kind S(n,k): ways to partition n elements into k non-empty subsets
    public long stirling(int n, int k) {
        long[][] dp = new long[n + 1][k + 1];
        dp[0][0] = 1;
        for (int i = 1; i <= n; i++)
            for (int j = 1; j <= Math.min(i, k); j++)
                dp[i][j] = j * dp[i-1][j] + dp[i-1][j-1];
        return dp[n][k];
    }

    public static void main(String[] args) {
        Problem45_StirlingNumbers sol = new Problem45_StirlingNumbers();
        System.out.println(sol.stirling(5, 3)); // 25
    }
}
