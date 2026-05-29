import java.util.Arrays;

public class Problem08_PartitionToKEqualSumSubsets {
    public boolean canPartitionKSubsets(int[] nums, int k) {
        int sum = Arrays.stream(nums).sum();
        if (sum % k != 0) return false;
        int target = sum / k;
        int n = nums.length;
        boolean[] dp = new boolean[1 << n];
        int[] subsetSum = new int[1 << n];
        dp[0] = true;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (!dp[mask]) continue;
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                int next = mask | (1 << i);
                if (subsetSum[mask] % target + nums[i] <= target) {
                    dp[next] = true;
                    subsetSum[next] = subsetSum[mask] + nums[i];
                }
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem08_PartitionToKEqualSumSubsets().canPartitionKSubsets(new int[]{4,3,2,3,5,2,1}, 4));
    }
}
