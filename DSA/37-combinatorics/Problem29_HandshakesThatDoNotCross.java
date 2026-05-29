public class Problem29_HandshakesThatDoNotCross {
    // Catalan number C(n) where 2n people
    public int numberOfWays(int numPeople) {
        long MOD = 1_000_000_007;
        int n = numPeople / 2;
        long[] dp = new long[n + 1];
        dp[0] = 1;
        for (int i = 1; i <= n; i++)
            for (int j = 0; j < i; j++)
                dp[i] = (dp[i] + dp[j] * dp[i-1-j]) % MOD;
        return (int) dp[n];
    }

    public static void main(String[] args) {
        System.out.println(new Problem29_HandshakesThatDoNotCross().numberOfWays(6)); // 5
    }
}
