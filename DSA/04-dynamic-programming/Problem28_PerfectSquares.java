/**
 * Problem 28: Perfect Squares
 * 
 * Find least number of perfect square numbers that sum to n.
 * 
 * State: dp[i] = min perfect squares summing to i
 * Recurrence: dp[i] = min(dp[i - j*j] + 1) for all j where j*j <= i
 * 
 * Time: O(n*sqrt(n)), Space: O(n)
 */
public class Problem28_PerfectSquares {

    public static int numSquares(int n) {
        int[] dp = new int[n + 1];
        java.util.Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j * j <= i; j++) {
                dp[i] = Math.min(dp[i], dp[i - j * j] + 1);
            }
        }
        return dp[n];
    }

    public static void main(String[] args) {
        System.out.println("=== Perfect Squares ===");
        System.out.println(numSquares(12)); // 3 (4+4+4)
        System.out.println(numSquares(13)); // 2 (4+9)
    }
}
