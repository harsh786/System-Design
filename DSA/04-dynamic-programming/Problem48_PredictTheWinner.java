/**
 * Problem 48: Predict the Winner
 * 
 * Two players pick from either end. Player 1 goes first. Can Player 1 win (or tie)?
 * 
 * State: dp[i][j] = max score difference current player can achieve from nums[i..j]
 * Same as Stone Game but allows tie (>=0 means Player 1 wins).
 * 
 * Time: O(n^2), Space: O(n)
 */
public class Problem48_PredictTheWinner {

    public static boolean predictTheWinner(int[] nums) {
        int n = nums.length;
        int[] dp = nums.clone();
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i + len - 1 < n; i++) {
                int j = i + len - 1;
                dp[i] = Math.max(nums[i] - dp[i + 1], nums[j] - dp[i]);
            }
        }
        return dp[0] >= 0;
    }

    public static void main(String[] args) {
        System.out.println("=== Predict the Winner ===");
        System.out.println(predictTheWinner(new int[]{1,5,2})); // false
        System.out.println(predictTheWinner(new int[]{1,5,233,7})); // true
    }
}
