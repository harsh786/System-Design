public class Problem27_PredictTheWinner {
    // LC 486
    static boolean predictTheWinner(int[] nums) {
        int n = nums.length;
        int[][] dp = new int[n][n];
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
        System.out.println(predictTheWinner(new int[]{1,5,2})); // false
        System.out.println(predictTheWinner(new int[]{1,5,233,7})); // true
    }
}
