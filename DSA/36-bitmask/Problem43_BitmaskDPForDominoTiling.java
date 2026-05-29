public class Problem43_BitmaskDPForDominoTiling {
    // Count ways to tile an MxN grid with dominoes using profile DP
    public long countTilings(int m, int n) {
        if (m > n) { int t = m; m = n; n = t; }
        int states = 1 << m;
        long[] dp = new long[states];
        dp[states - 1] = 1;
        for (int col = 0; col < n; col++) {
            for (int row = 0; row < m; row++) {
                long[] ndp = new long[states];
                for (int mask = 0; mask < states; mask++) {
                    if (dp[mask] == 0) continue;
                    if ((mask & (1 << row)) != 0) {
                        // already filled, move on
                        ndp[mask ^ (1 << row)] += dp[mask];
                    } else {
                        // place horizontal domino (extends to next column)
                        ndp[mask | (1 << row)] += dp[mask];
                        // place vertical domino
                        if (row + 1 < m && (mask & (1 << (row + 1))) == 0)
                            ndp[mask | (1 << (row + 1))] += dp[mask];
                    }
                }
                dp = ndp;
            }
        }
        return dp[0];
    }

    public static void main(String[] args) {
        System.out.println(new Problem43_BitmaskDPForDominoTiling().countTilings(2, 4)); // Should be related to tiling count
    }
}
