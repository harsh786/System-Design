/**
 * Problem 14: Target Sum
 * 
 * Assign + or - to each number to reach target sum. Count ways.
 * Transform: find subset with sum = (total + target) / 2
 * 
 * Time: O(n * sum), Space: O(sum)
 * 
 * Production Analogy: Like feature flag combinations - how many ways can you
 * enable/disable features to reach a specific performance target.
 */
public class Problem14_TargetSum {

    public static int findTargetSumWays(int[] nums, int target) {
        int sum = 0;
        for (int n : nums) sum += n;
        if ((sum + target) % 2 != 0 || sum + target < 0) return 0;
        int subsetSum = (sum + target) / 2;
        if (subsetSum < 0) return 0;
        int[] dp = new int[subsetSum + 1];
        dp[0] = 1;
        for (int num : nums) {
            for (int j = subsetSum; j >= num; j--) {
                dp[j] += dp[j - num];
            }
        }
        return dp[subsetSum];
    }

    public static void main(String[] args) {
        System.out.println("=== Target Sum ===");
        System.out.println(findTargetSumWays(new int[]{1,1,1,1,1}, 3)); // 5
        System.out.println(findTargetSumWays(new int[]{1}, 1)); // 1
        System.out.println(findTargetSumWays(new int[]{0,0,0,0,0,0,0,0,1}, 1)); // 256
    }
}
