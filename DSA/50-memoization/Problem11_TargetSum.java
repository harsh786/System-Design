import java.util.*;

public class Problem11_TargetSum {
    private Map<String, Integer> memo = new HashMap<>();

    public int findTargetSumWays(int[] nums, int target) {
        return helper(nums, 0, 0, target);
    }

    private int helper(int[] nums, int i, int sum, int target) {
        if (i == nums.length) return sum == target ? 1 : 0;
        String key = i + "," + sum;
        if (memo.containsKey(key)) return memo.get(key);
        int result = helper(nums, i + 1, sum + nums[i], target) + helper(nums, i + 1, sum - nums[i], target);
        memo.put(key, result);
        return result;
    }

    public static void main(String[] args) {
        Problem11_TargetSum sol = new Problem11_TargetSum();
        System.out.println("Target Sum [1,1,1,1,1] target=3: " + sol.findTargetSumWays(new int[]{1,1,1,1,1}, 3)); // 5
    }
}
