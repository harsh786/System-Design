/**
 * Problem 43: Partition to K Equal Sum Subsets
 * 
 * Approach: Same as matchsticks but with K sides. dp[mask] = remainder in current bucket.
 * Time: O(n * 2^n), Space: O(2^n)
 * 
 * Production Analogy: Balanced sharding of data across K partitions.
 */
import java.util.*;

public class Problem43_PartitionToKEqualSumSubsets {
    public static boolean canPartitionKSubsets(int[] nums, int k) {
        int sum = Arrays.stream(nums).sum();
        if (sum % k != 0) return false;
        int target = sum / k, n = nums.length;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, -1);
        dp[0] = 0;
        Arrays.sort(nums);
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == -1) continue;
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                if (dp[mask] + nums[i] <= target) {
                    dp[mask | (1 << i)] = (dp[mask] + nums[i]) % target;
                }
            }
        }
        return dp[(1 << n) - 1] == 0;
    }

    public static void main(String[] args) {
        System.out.println(canPartitionKSubsets(new int[]{4,3,2,3,5,2,1}, 4)); // true
        System.out.println(canPartitionKSubsets(new int[]{1,2,3,4}, 3)); // false
    }
}
