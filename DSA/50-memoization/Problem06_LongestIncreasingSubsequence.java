import java.util.*;

public class Problem06_LongestIncreasingSubsequence {
    private int[] memo;

    public int lengthOfLIS(int[] nums) {
        memo = new int[nums.length];
        Arrays.fill(memo, -1);
        int max = 0;
        for (int i = 0; i < nums.length; i++) max = Math.max(max, helper(nums, i));
        return max;
    }

    private int helper(int[] nums, int i) {
        if (memo[i] != -1) return memo[i];
        int best = 1;
        for (int j = 0; j < i; j++) {
            if (nums[j] < nums[i]) best = Math.max(best, 1 + helper(nums, j));
        }
        memo[i] = best;
        return best;
    }

    public static void main(String[] args) {
        Problem06_LongestIncreasingSubsequence sol = new Problem06_LongestIncreasingSubsequence();
        System.out.println("LIS [10,9,2,5,3,7,101,18]: " + sol.lengthOfLIS(new int[]{10,9,2,5,3,7,101,18})); // 4
    }
}
