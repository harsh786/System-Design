import java.util.*;

public class Problem03_PredictTheWinner {
    // 486. Predict the Winner: Array of scores, two players pick from either end.
    // Return true if player 1 can win (score >= player 2's score).
    
    public boolean predictTheWinner(int[] nums) {
        int n = nums.length;
        int[][] dp = new int[n][n];
        // dp[i][j] = max score difference the current player can achieve from nums[i..j]
        for (int i = 0; i < n; i++) dp[i][i] = nums[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                dp[i][j] = Math.max(nums[i] - dp[i+1][j], nums[j] - dp[i][j-1]);
            }
        }
        return dp[0][n-1] >= 0;
    }
    
    public static void main(String[] args) {
        Problem03_PredictTheWinner sol = new Problem03_PredictTheWinner();
        System.out.println(sol.predictTheWinner(new int[]{1,5,2}));   // false
        System.out.println(sol.predictTheWinner(new int[]{1,5,233,7})); // true
    }
}
