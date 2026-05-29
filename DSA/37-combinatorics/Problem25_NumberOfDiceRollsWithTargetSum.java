public class Problem25_NumberOfDiceRollsWithTargetSum {
    public int numRollsToTarget(int n, int k, int target) {
        long MOD = 1_000_000_007;
        long[] dp = new long[target + 1];
        dp[0] = 1;
        for (int i = 0; i < n; i++) {
            long[] ndp = new long[target + 1];
            for (int j = 1; j <= target; j++)
                for (int f = 1; f <= k && f <= j; f++)
                    ndp[j] = (ndp[j] + dp[j - f]) % MOD;
            dp = ndp;
        }
        return (int) dp[target];
    }

    public static void main(String[] args) {
        System.out.println(new Problem25_NumberOfDiceRollsWithTargetSum().numRollsToTarget(2, 6, 7));
    }
}
