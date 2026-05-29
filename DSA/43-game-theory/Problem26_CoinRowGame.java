import java.util.*;

public class Problem26_CoinRowGame {
    // Coin Row: Pick coins from a row, cannot pick adjacent. Maximize total (single player).
    // Then extend to adversarial version.
    
    public int coinRowSingle(int[] coins) {
        int n = coins.length;
        if (n == 0) return 0;
        if (n == 1) return coins[0];
        int prev2 = 0, prev1 = coins[0];
        for (int i = 1; i < n; i++) {
            int cur = Math.max(prev1, prev2 + coins[i]);
            prev2 = prev1;
            prev1 = cur;
        }
        return prev1;
    }
    
    // Two player version: pick from ends (standard interval DP)
    public int coinRowTwoPlayer(int[] coins) {
        int n = coins.length;
        int[][] dp = new int[n][n];
        for (int i = 0; i < n; i++) dp[i][i] = coins[i];
        for (int len = 2; len <= n; len++)
            for (int i = 0; i <= n-len; i++) {
                int j = i+len-1;
                dp[i][j] = Math.max(coins[i] - dp[i+1][j], coins[j] - dp[i][j-1]);
            }
        return dp[0][n-1];
    }
    
    public static void main(String[] args) {
        Problem26_CoinRowGame sol = new Problem26_CoinRowGame();
        System.out.println(sol.coinRowSingle(new int[]{5,1,2,10,6,2})); // 17
        System.out.println(sol.coinRowTwoPlayer(new int[]{5,3,7,10}));  // 2
    }
}
