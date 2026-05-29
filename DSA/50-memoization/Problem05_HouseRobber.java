import java.util.*;

public class Problem05_HouseRobber {
    private Map<Integer, Integer> memo = new HashMap<>();

    public int rob(int[] nums) {
        return helper(nums, 0);
    }

    private int helper(int[] nums, int i) {
        if (i >= nums.length) return 0;
        if (memo.containsKey(i)) return memo.get(i);
        int result = Math.max(nums[i] + helper(nums, i + 2), helper(nums, i + 1));
        memo.put(i, result);
        return result;
    }

    public static void main(String[] args) {
        Problem05_HouseRobber sol = new Problem05_HouseRobber();
        System.out.println("Rob [2,7,9,3,1]: " + sol.rob(new int[]{2,7,9,3,1})); // 12
    }
}
