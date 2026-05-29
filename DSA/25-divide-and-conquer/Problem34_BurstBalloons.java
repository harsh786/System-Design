/**
 * Problem 34: Burst Balloons (LeetCode 312) - Interval Split D&C
 * 
 * D&C Approach:
 * - DIVIDE: For interval [left, right], try each balloon k as the LAST one to burst
 * - CONQUER: Recursively solve [left, k] and [k, right]
 * - COMBINE: Total = left_result + nums[left]*nums[k]*nums[right] + right_result
 * 
 * Key insight: choosing k as the LAST balloon to burst means left/right are independent
 * 
 * Time: O(n^3) with memoization, Space: O(n^2)
 * 
 * Production Analogy:
 * - Resource deallocation ordering for maximum benefit
 * - Optimal job scheduling with dependency chains
 * - Game theory: choosing order of moves for maximum score
 */
public class Problem34_BurstBalloons {

    public static int maxCoins(int[] nums) {
        int n = nums.length;
        int[] balloons = new int[n + 2];
        balloons[0] = balloons[n + 1] = 1;
        for (int i = 0; i < n; i++) balloons[i + 1] = nums[i];
        
        int[][] dp = new int[n + 2][n + 2];
        // Interval DP: length from 2 to n+2
        for (int len = 2; len <= n + 1; len++) {
            for (int left = 0; left + len <= n + 1; left++) {
                int right = left + len;
                for (int k = left + 1; k < right; k++) {
                    int coins = balloons[left] * balloons[k] * balloons[right];
                    dp[left][right] = Math.max(dp[left][right], dp[left][k] + coins + dp[k][right]);
                }
            }
        }
        return dp[0][n + 1];
    }

    // Recursive with memoization (pure D&C style)
    public static int maxCoinsRecursive(int[] nums) {
        int n = nums.length;
        int[] b = new int[n + 2];
        b[0] = b[n + 1] = 1;
        for (int i = 0; i < n; i++) b[i + 1] = nums[i];
        int[][] memo = new int[n + 2][n + 2];
        return solve(b, memo, 0, n + 1);
    }

    private static int solve(int[] b, int[][] memo, int left, int right) {
        if (right - left <= 1) return 0;
        if (memo[left][right] > 0) return memo[left][right];
        for (int k = left + 1; k < right; k++) {
            int val = solve(b, memo, left, k) + b[left] * b[k] * b[right] + solve(b, memo, k, right);
            memo[left][right] = Math.max(memo[left][right], val);
        }
        return memo[left][right];
    }

    public static void main(String[] args) {
        System.out.println(maxCoins(new int[]{3, 1, 5, 8}));     // 167
        System.out.println(maxCoins(new int[]{1, 5}));            // 10
        System.out.println(maxCoinsRecursive(new int[]{3, 1, 5, 8})); // 167
        System.out.println(maxCoins(new int[]{9, 76, 64, 21}));  // 116718
    }
}
