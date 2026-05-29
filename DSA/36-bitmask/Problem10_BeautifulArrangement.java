public class Problem10_BeautifulArrangement {
    public int countArrangement(int n) {
        int[] dp = new int[1 << n];
        dp[0] = 1;
        for (int mask = 0; mask < (1 << n); mask++) {
            int pos = Integer.bitCount(mask) + 1;
            if (dp[mask] == 0) continue;
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                if ((i + 1) % pos == 0 || pos % (i + 1) == 0)
                    dp[mask | (1 << i)] += dp[mask];
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem10_BeautifulArrangement().countArrangement(6));
    }
}
