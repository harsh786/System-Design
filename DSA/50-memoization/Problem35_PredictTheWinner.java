import java.util.*;

public class Problem35_PredictTheWinner {
    private Integer[][] memo;

    public boolean predictTheWinner(int[] nums) {
        int n = nums.length;
        memo = new Integer[n][n];
        return helper(nums, 0, n - 1) >= 0;
    }

    private int helper(int[] nums, int l, int r) {
        if (l == r) return nums[l];
        if (memo[l][r] != null) return memo[l][r];
        memo[l][r] = Math.max(nums[l] - helper(nums, l+1, r), nums[r] - helper(nums, l, r-1));
        return memo[l][r];
    }

    public static void main(String[] args) {
        Problem35_PredictTheWinner sol = new Problem35_PredictTheWinner();
        System.out.println(sol.predictTheWinner(new int[]{1,5,233,7})); // true
    }
}
