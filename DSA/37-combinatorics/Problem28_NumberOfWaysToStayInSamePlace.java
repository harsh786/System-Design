public class Problem28_NumberOfWaysToStayInSamePlace {
    public int numWays(int steps, int arrLen) {
        long MOD = 1_000_000_007;
        int maxPos = Math.min(arrLen, steps / 2 + 1);
        long[] dp = new long[maxPos];
        dp[0] = 1;
        for (int s = 0; s < steps; s++) {
            long[] ndp = new long[maxPos];
            for (int i = 0; i < maxPos; i++) {
                ndp[i] = dp[i];
                if (i > 0) ndp[i] = (ndp[i] + dp[i-1]) % MOD;
                if (i < maxPos - 1) ndp[i] = (ndp[i] + dp[i+1]) % MOD;
            }
            dp = ndp;
        }
        return (int) dp[0];
    }

    public static void main(String[] args) {
        System.out.println(new Problem28_NumberOfWaysToStayInSamePlace().numWays(3, 2));
    }
}
