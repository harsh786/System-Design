import java.util.*;

public class Problem16_AdversarialCoinRow {
    // Adversarial Coin Row: Coins in a row, two players pick from either end.
    // Both play optimally. Return first player's max collection.
    
    public int maxCoin(int[] coins) {
        int n = coins.length;
        int[][] dp = new int[n][n];
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + coins[i];
        
        // dp[i][j] = first player max from coins[i..j]
        for (int i = 0; i < n; i++) dp[i][i] = coins[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                int total = prefix[j+1] - prefix[i];
                // current player takes left or right, opponent gets optimal of remainder
                dp[i][j] = total - Math.min(dp[i+1][j], dp[i][j-1]);
            }
        }
        return dp[0][n-1];
    }
    
    public static void main(String[] args) {
        Problem16_AdversarialCoinRow sol = new Problem16_AdversarialCoinRow();
        System.out.println(sol.maxCoin(new int[]{20,30,2,2,2,10})); // 42
    }
}
