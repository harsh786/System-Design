import java.util.*;

public class Problem09_GuessNumberHigherOrLowerII {
    // 375. Guess Number Higher or Lower II: Pick a number 1..n. When wrong, pay the guessed amount.
    // Find minimum money needed to guarantee a win (minimax).
    
    public int getMoneyAmount(int n) {
        int[][] dp = new int[n + 2][n + 2];
        for (int len = 2; len <= n; len++) {
            for (int i = 1; i <= n - len + 1; i++) {
                int j = i + len - 1;
                dp[i][j] = Integer.MAX_VALUE;
                for (int k = i; k <= j; k++) {
                    int cost = k + Math.max(dp[i][k-1], dp[k+1][j]);
                    dp[i][j] = Math.min(dp[i][j], cost);
                }
            }
        }
        return dp[1][n];
    }
    
    public static void main(String[] args) {
        Problem09_GuessNumberHigherOrLowerII sol = new Problem09_GuessNumberHigherOrLowerII();
        System.out.println(sol.getMoneyAmount(10)); // 16
        System.out.println(sol.getMoneyAmount(1));  // 0
        System.out.println(sol.getMoneyAmount(2));  // 1
    }
}
