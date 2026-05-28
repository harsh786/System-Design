/**
 * Problem 1: Climbing Stairs
 * 
 * You are climbing a staircase. It takes n steps to reach the top.
 * Each time you can climb 1 or 2 steps. How many distinct ways can you climb to the top?
 * 
 * State Definition: dp[i] = number of distinct ways to reach step i
 * Recurrence: dp[i] = dp[i-1] + dp[i-2]
 * Base Cases: dp[0] = 1, dp[1] = 1
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n) for tabulation, O(1) optimized
 * 
 * Production Analogy: Like counting deployment paths in a CI/CD pipeline where each stage
 * can be skipped or executed, and you need to know total valid pipeline configurations.
 */
public class Problem01_ClimbingStairs {

    // Top-down with memoization
    public static int climbStairsMemo(int n) {
        int[] memo = new int[n + 1];
        return helper(n, memo);
    }

    private static int helper(int n, int[] memo) {
        if (n <= 1) return 1;
        if (memo[n] != 0) return memo[n];
        memo[n] = helper(n - 1, memo) + helper(n - 2, memo);
        return memo[n];
    }

    // Bottom-up tabulation
    public static int climbStairsTab(int n) {
        if (n <= 1) return 1;
        int[] dp = new int[n + 1];
        dp[0] = 1;
        dp[1] = 1;
        for (int i = 2; i <= n; i++) {
            dp[i] = dp[i - 1] + dp[i - 2];
        }
        return dp[n];
    }

    // Space-optimized
    public static int climbStairsOpt(int n) {
        if (n <= 1) return 1;
        int prev2 = 1, prev1 = 1;
        for (int i = 2; i <= n; i++) {
            int curr = prev1 + prev2;
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== Climbing Stairs ===");
        int[] tests = {1, 2, 3, 5, 10, 30};
        for (int n : tests) {
            System.out.printf("n=%d: memo=%d, tab=%d, opt=%d%n",
                n, climbStairsMemo(n), climbStairsTab(n), climbStairsOpt(n));
        }
    }
}
