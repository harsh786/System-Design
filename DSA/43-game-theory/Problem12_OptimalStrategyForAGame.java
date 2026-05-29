import java.util.*;

public class Problem12_OptimalStrategyForAGame {
    // Optimal Strategy: coins in a line, pick from either end. Maximize your total.
    // Same as Predict the Winner but returns the actual max value for first player.
    
    public int optimalStrategy(int[] coins) {
        int n = coins.length;
        int[][] dp = new int[n][n];
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + coins[i];
        
        for (int i = 0; i < n; i++) dp[i][i] = coins[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                int total = prefix[j+1] - prefix[i];
                dp[i][j] = total - Math.min(dp[i+1][j], dp[i][j-1]);
            }
        }
        return dp[0][n-1];
    }
    
    public static void main(String[] args) {
        Problem12_OptimalStrategyForAGame sol = new Problem12_OptimalStrategyForAGame();
        System.out.println(sol.optimalStrategy(new int[]{5,3,7,10})); // 15
        System.out.println(sol.optimalStrategy(new int[]{8,15,3,7})); // 22
    }
}
