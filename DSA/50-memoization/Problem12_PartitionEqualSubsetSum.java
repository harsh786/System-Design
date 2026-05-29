import java.util.*;

public class Problem12_PartitionEqualSubsetSum {
    private Boolean[][] memo;

    public boolean canPartition(int[] nums) {
        int sum = 0;
        for (int n : nums) sum += n;
        if (sum % 2 != 0) return false;
        memo = new Boolean[nums.length][sum / 2 + 1];
        return helper(nums, 0, sum / 2);
    }

    private boolean helper(int[] nums, int i, int target) {
        if (target == 0) return true;
        if (i >= nums.length || target < 0) return false;
        if (memo[i][target] != null) return memo[i][target];
        memo[i][target] = helper(nums, i + 1, target - nums[i]) || helper(nums, i + 1, target);
        return memo[i][target];
    }

    public static void main(String[] args) {
        Problem12_PartitionEqualSubsetSum sol = new Problem12_PartitionEqualSubsetSum();
        System.out.println(sol.canPartition(new int[]{1,5,11,5})); // true
    }
}
