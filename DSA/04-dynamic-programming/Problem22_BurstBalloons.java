/**
 * Problem 22: Burst Balloons
 * 
 * Burst balloons to maximize coins. Bursting balloon i gives nums[left]*nums[i]*nums[right].
 * 
 * State: dp[i][j] = max coins from bursting all balloons between i and j (exclusive)
 * Recurrence: dp[i][j] = max(dp[i][k] + dp[k][j] + nums[i]*nums[k]*nums[j]) for i < k < j
 * Key insight: k is the LAST balloon burst in range (i,j)
 * 
 * Time: O(n^3), Space: O(n^2)
 */
public class Problem22_BurstBalloons {

    public static int maxCoins(int[] nums) {
        int n = nums.length;
        int[] arr = new int[n + 2];
        arr[0] = arr[n + 1] = 1;
        for (int i = 0; i < n; i++) arr[i + 1] = nums[i];
        int len = n + 2;
        int[][] dp = new int[len][len];
        for (int gap = 2; gap < len; gap++) {
            for (int i = 0; i + gap < len; i++) {
                int j = i + gap;
                for (int k = i + 1; k < j; k++) {
                    dp[i][j] = Math.max(dp[i][j], dp[i][k] + dp[k][j] + arr[i] * arr[k] * arr[j]);
                }
            }
        }
        return dp[0][len - 1];
    }

    public static void main(String[] args) {
        System.out.println("=== Burst Balloons ===");
        System.out.println(maxCoins(new int[]{3,1,5,8})); // 167
        System.out.println(maxCoins(new int[]{1,5})); // 10
    }
}
