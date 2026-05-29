public class Problem49_SOSDPSumOverSubsets {
    // Sum over Subsets DP: for each mask, compute sum of f[sub] for all sub that are subsets of mask
    public int[] sosDP(int[] f, int n) {
        int[] dp = f.clone();
        for (int i = 0; i < n; i++)
            for (int mask = 0; mask < (1 << n); mask++)
                if ((mask & (1 << i)) != 0)
                    dp[mask] += dp[mask ^ (1 << i)];
        return dp;
    }

    public static void main(String[] args) {
        // f[mask] = mask for demo
        int n = 3;
        int[] f = new int[1 << n];
        for (int i = 0; i < (1 << n); i++) f[i] = i;
        int[] result = new Problem49_SOSDPSumOverSubsets().sosDP(f, n);
        System.out.println("SOS DP results:");
        for (int i = 0; i < (1 << n); i++)
            System.out.println("  dp[" + Integer.toBinaryString(i) + "] = " + result[i]);
    }
}
