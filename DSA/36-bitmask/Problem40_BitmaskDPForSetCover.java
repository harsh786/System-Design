import java.util.Arrays;

public class Problem40_BitmaskDPForSetCover {
    // Minimum number of sets to cover all elements
    public int minSetCover(int n, int[][] sets) {
        int m = sets.length;
        int[] setMask = new int[m];
        for (int i = 0; i < m; i++) for (int e : sets[i]) setMask[i] |= (1 << e);
        int full = (1 << n) - 1;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == Integer.MAX_VALUE) continue;
            for (int i = 0; i < m; i++)
                dp[mask | setMask[i]] = Math.min(dp[mask | setMask[i]], dp[mask] + 1);
        }
        return dp[full] == Integer.MAX_VALUE ? -1 : dp[full];
    }

    public static void main(String[] args) {
        int[][] sets = {{0,1,2},{1,3},{2,4},{3,4}};
        System.out.println(new Problem40_BitmaskDPForSetCover().minSetCover(5, sets)); // 2
    }
}
