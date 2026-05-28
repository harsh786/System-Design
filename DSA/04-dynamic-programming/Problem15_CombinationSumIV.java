/**
 * Problem 15: Combination Sum IV
 * 
 * Given array of distinct integers and target, find number of combinations that sum to target.
 * (Order matters - this is actually permutations)
 * 
 * State: dp[i] = number of combinations that sum to i
 * Recurrence: dp[i] = sum(dp[i - num]) for each num in nums where num <= i
 * 
 * Time: O(target * n), Space: O(target)
 */
public class Problem15_CombinationSumIV {

    public static int combinationSum4(int[] nums, int target) {
        int[] dp = new int[target + 1];
        dp[0] = 1;
        for (int i = 1; i <= target; i++) {
            for (int num : nums) {
                if (num <= i) dp[i] += dp[i - num];
            }
        }
        return dp[target];
    }

    public static void main(String[] args) {
        System.out.println("=== Combination Sum IV ===");
        System.out.println(combinationSum4(new int[]{1,2,3}, 4)); // 7
        System.out.println(combinationSum4(new int[]{9}, 3)); // 0
    }
}
