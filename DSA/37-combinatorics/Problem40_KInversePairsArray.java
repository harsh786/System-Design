public class Problem40_KInversePairsArray {
    public int kInversePairs(int n, int k) {
        long MOD = 1_000_000_007;
        long[] dp = new long[k + 1];
        dp[0] = 1;
        for (int i = 2; i <= n; i++) {
            long[] ndp = new long[k + 1];
            long[] prefix = new long[k + 2];
            for (int j = 0; j <= k; j++) prefix[j + 1] = prefix[j] + dp[j];
            for (int j = 0; j <= k; j++) {
                ndp[j] = (prefix[j + 1] - prefix[Math.max(0, j - i + 1)] + MOD) % MOD;
            }
            dp = ndp;
        }
        return (int) dp[k];
    }

    public static void main(String[] args) {
        System.out.println(new Problem40_KInversePairsArray().kInversePairs(3, 1)); // 2
    }
}
