/**
 * Problem 30: Rod Cutting
 * 
 * Given a rod of length n and prices for each length, find max revenue.
 * Unbounded knapsack variant.
 * 
 * State: dp[i] = max revenue from rod of length i
 * Recurrence: dp[i] = max(price[j] + dp[i-j-1]) for j = 0..i-1
 * 
 * Time: O(n^2), Space: O(n)
 */
public class Problem30_RodCutting {

    public static int cutRod(int[] prices, int n) {
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= i; j++) {
                dp[i] = Math.max(dp[i], prices[j - 1] + dp[i - j]);
            }
        }
        return dp[n];
    }

    public static void main(String[] args) {
        System.out.println("=== Rod Cutting ===");
        System.out.println(cutRod(new int[]{1,5,8,9,10,17,17,20}, 8)); // 22
        System.out.println(cutRod(new int[]{3,5,8,9,10,17,17,20}, 8)); // 24
    }
}
