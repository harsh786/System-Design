public class Problem24_GuessNumberHigherOrLowerII {
    // LC 375: Minimize worst-case cost (pay the number you guess wrong)
    static int getMoneyAmount(int n) {
        int[][] dp = new int[n + 2][n + 2];
        for (int len = 2; len <= n; len++) {
            for (int i = 1; i <= n - len + 1; i++) {
                int j = i + len - 1;
                dp[i][j] = Integer.MAX_VALUE;
                for (int k = i; k <= j; k++)
                    dp[i][j] = Math.min(dp[i][j], k + Math.max(dp[i][k-1], dp[k+1][j]));
            }
        }
        return dp[1][n];
    }
    
    public static void main(String[] args) {
        System.out.println("n=10: " + getMoneyAmount(10)); // 16
    }
}
