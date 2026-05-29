public class Problem26_KnightDialer {
    public int knightDialer(int n) {
        long MOD = 1_000_000_007;
        int[][] moves = {{4,6},{6,8},{7,9},{4,8},{0,3,9},{},{0,1,7},{2,6},{1,3},{2,4}};
        long[] dp = new long[10];
        java.util.Arrays.fill(dp, 1);
        for (int k = 1; k < n; k++) {
            long[] ndp = new long[10];
            for (int i = 0; i < 10; i++)
                for (int j : moves[i]) ndp[i] = (ndp[i] + dp[j]) % MOD;
            dp = ndp;
        }
        long sum = 0;
        for (long v : dp) sum = (sum + v) % MOD;
        return (int) sum;
    }

    public static void main(String[] args) {
        System.out.println(new Problem26_KnightDialer().knightDialer(3131));
    }
}
