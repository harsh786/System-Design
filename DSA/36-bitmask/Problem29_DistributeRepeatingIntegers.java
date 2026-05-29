import java.util.*;

public class Problem29_DistributeRepeatingIntegers {
    public boolean canDistribute(int[] nums, int[] quantity) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        int[] counts = freq.values().stream().mapToInt(Integer::intValue).toArray();
        int m = quantity.length;
        int[] subSum = new int[1 << m];
        for (int mask = 1; mask < (1 << m); mask++) {
            int lsb = Integer.numberOfTrailingZeros(mask);
            subSum[mask] = subSum[mask ^ (1 << lsb)] + quantity[lsb];
        }
        int n2 = counts.length;
        boolean[][] dp = new boolean[n2 + 1][1 << m];
        dp[0][0] = true;
        for (int i = 1; i <= n2; i++) {
            for (int mask = 0; mask < (1 << m); mask++) {
                dp[i][mask] = dp[i-1][mask];
                for (int sub = mask; sub > 0 && !dp[i][mask]; sub = (sub - 1) & mask)
                    if (subSum[sub] <= counts[i-1] && dp[i-1][mask ^ sub]) dp[i][mask] = true;
            }
        }
        return dp[n2][(1 << m) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem29_DistributeRepeatingIntegers().canDistribute(new int[]{1,2,3,4}, new int[]{2}));
    }
}
