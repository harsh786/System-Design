public class Problem32_ProfitableSchemes {
    public int profitableSchemes(int n, int minProfit, int[] group, int[] profit) {
        long MOD = 1_000_000_007;
        long[][] dp = new long[n + 1][minProfit + 1];
        dp[0][0] = 1;
        for (int k = 0; k < group.length; k++) {
            int g = group[k], p = profit[k];
            for (int i = n; i >= g; i--)
                for (int j = minProfit; j >= 0; j--)
                    dp[i][Math.min(minProfit, j + p)] = (dp[i][Math.min(minProfit, j + p)] + dp[i - g][j]) % MOD;
        }
        long result = 0;
        for (int i = 0; i <= n; i++) result = (result + dp[i][minProfit]) % MOD;
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem32_ProfitableSchemes().profitableSchemes(5, 3, new int[]{2,2}, new int[]{2,3}));
    }
}
