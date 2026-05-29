import java.util.*;

public class Problem25_PredictTheWinnerWithMemoization {
    // Predict the Winner with top-down memoization approach.
    
    public boolean predictTheWinner(int[] nums) {
        int n = nums.length;
        Integer[][] memo = new Integer[n][n];
        int total = 0;
        for (int x : nums) total += x;
        int firstPlayer = solve(nums, 0, n-1, memo);
        return firstPlayer >= total - firstPlayer;
    }
    
    private int solve(int[] nums, int i, int j, Integer[][] memo) {
        if (i > j) return 0;
        if (i == j) return nums[i];
        if (memo[i][j] != null) return memo[i][j];
        int pickLeft = nums[i] + Math.min(solve(nums, i+2, j, memo), solve(nums, i+1, j-1, memo));
        int pickRight = nums[j] + Math.min(solve(nums, i+1, j-1, memo), solve(nums, i, j-2, memo));
        memo[i][j] = Math.max(pickLeft, pickRight);
        return memo[i][j];
    }
    
    public static void main(String[] args) {
        Problem25_PredictTheWinnerWithMemoization sol = new Problem25_PredictTheWinnerWithMemoization();
        System.out.println(sol.predictTheWinner(new int[]{1,5,2}));     // false
        System.out.println(sol.predictTheWinner(new int[]{1,5,233,7})); // true
    }
}
