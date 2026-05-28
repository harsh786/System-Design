/**
 * Problem 13: Partition Equal Subset Sum
 * 
 * Can you partition array into two subsets with equal sum?
 * Equivalent to: does a subset exist with sum = totalSum/2?
 * 
 * State: dp[j] = true if subset with sum j exists
 * Time: O(n * sum), Space: O(sum)
 * 
 * Production Analogy: Like load balancing - can you split tasks into two servers
 * with exactly equal load?
 */
public class Problem13_PartitionEqualSubsetSum {

    public static boolean canPartition(int[] nums) {
        int sum = 0;
        for (int n : nums) sum += n;
        if (sum % 2 != 0) return false;
        int target = sum / 2;
        boolean[] dp = new boolean[target + 1];
        dp[0] = true;
        for (int num : nums) {
            for (int j = target; j >= num; j--) {
                dp[j] = dp[j] || dp[j - num];
            }
        }
        return dp[target];
    }

    public static void main(String[] args) {
        System.out.println("=== Partition Equal Subset Sum ===");
        System.out.println(canPartition(new int[]{1,5,11,5})); // true
        System.out.println(canPartition(new int[]{1,2,3,5})); // false
        System.out.println(canPartition(new int[]{1,1})); // true
    }
}
