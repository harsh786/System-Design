/**
 * Problem 2: House Robber
 * 
 * Given an array representing money in each house, find max money you can rob
 * without robbing two adjacent houses.
 * 
 * State: dp[i] = max money robbing from houses 0..i
 * Recurrence: dp[i] = max(dp[i-1], dp[i-2] + nums[i])
 * 
 * Time: O(n), Space: O(1) optimized
 * 
 * Production Analogy: Like selecting non-conflicting jobs/resources to maximize throughput
 * where adjacent resources have conflicts.
 */
public class Problem02_HouseRobber {

    public static int robMemo(int[] nums) {
        int[] memo = new int[nums.length];
        java.util.Arrays.fill(memo, -1);
        return helper(nums, nums.length - 1, memo);
    }

    private static int helper(int[] nums, int i, int[] memo) {
        if (i < 0) return 0;
        if (memo[i] != -1) return memo[i];
        memo[i] = Math.max(helper(nums, i - 1, memo), helper(nums, i - 2, memo) + nums[i]);
        return memo[i];
    }

    public static int robTab(int[] nums) {
        if (nums.length == 0) return 0;
        if (nums.length == 1) return nums[0];
        int prev2 = 0, prev1 = 0;
        for (int num : nums) {
            int curr = Math.max(prev1, prev2 + num);
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== House Robber ===");
        int[][] tests = {{1,2,3,1}, {2,7,9,3,1}, {0}, {100}, {2,1,1,2}};
        for (int[] t : tests) {
            System.out.printf("%s: memo=%d, tab=%d%n",
                java.util.Arrays.toString(t), robMemo(t), robTab(t));
        }
    }
}
