import java.util.Arrays;

public class Problem28_MinimumIncompatibility {
    public int minimumIncompatibility(int[] nums, int k) {
        int n = nums.length, groupSize = n / k;
        Arrays.sort(nums);
        int[] cost = new int[1 << n];
        Arrays.fill(cost, -1);
        for (int mask = 0; mask < (1 << n); mask++) {
            if (Integer.bitCount(mask) != groupSize) continue;
            int min = 20, max = 0; boolean valid = true;
            int prev = -1;
            for (int i = 0; i < n; i++) if ((mask & (1 << i)) != 0) {
                if (nums[i] == prev) { valid = false; break; }
                prev = nums[i]; min = Math.min(min, nums[i]); max = Math.max(max, nums[i]);
            }
            if (valid) cost[mask] = max - min;
        }
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE / 2);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] >= Integer.MAX_VALUE / 2) continue;
            int remain = ((1 << n) - 1) ^ mask;
            for (int sub = remain; sub > 0; sub = (sub - 1) & remain) {
                if (cost[sub] >= 0) dp[mask | sub] = Math.min(dp[mask | sub], dp[mask] + cost[sub]);
            }
        }
        return dp[(1 << n) - 1] >= Integer.MAX_VALUE / 2 ? -1 : dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem28_MinimumIncompatibility().minimumIncompatibility(new int[]{1,2,1,4}, 2));
    }
}
