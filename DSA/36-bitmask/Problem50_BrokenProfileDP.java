public class Problem50_BrokenProfileDP {
    // Broken profile DP: count domino tilings of an M x N grid
    public long countTilings(int m, int n) {
        if ((m * n) % 2 != 0) return 0;
        if (m > n) { int t = m; m = n; n = t; }
        long[] dp = new long[1 << m];
        dp[(1 << m) - 1] = 1;
        for (int col = 0; col < n; col++) {
            for (int row = 0; row < m; row++) {
                long[] ndp = new long[1 << m];
                for (int mask = 0; mask < (1 << m); mask++) {
                    if (dp[mask] == 0) continue;
                    if ((mask & (1 << row)) != 0) {
                        ndp[mask ^ (1 << row)] += dp[mask]; // cell filled from prev col, skip
                    } else {
                        ndp[mask | (1 << row)] += dp[mask]; // horizontal: extends to next col
                        if (row + 1 < m && (mask & (1 << (row+1))) == 0)
                            ndp[mask | (1 << (row+1))] += dp[mask]; // vertical within this col
                    }
                }
                dp = ndp;
            }
        }
        return dp[0];
    }

    public static void main(String[] args) {
        System.out.println(new Problem50_BrokenProfileDP().countTilings(2, 3)); // 3
        System.out.println(new Problem50_BrokenProfileDP().countTilings(4, 4)); // 36 (known)
    }
}
