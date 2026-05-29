import java.util.*;

public class Problem04_StoneGame {
    // 877. Stone Game: Even number of piles, two players pick from ends.
    // Player with more stones wins. Can first player always win?
    // Answer: always true (first player can always pick all odd or all even indexed piles).
    // But here's the DP approach too.
    
    public boolean stoneGame(int[] piles) {
        int n = piles.length;
        int[][] dp = new int[n][n];
        for (int i = 0; i < n; i++) dp[i][i] = piles[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                dp[i][j] = Math.max(piles[i] - dp[i+1][j], piles[j] - dp[i][j-1]);
            }
        }
        return dp[0][n-1] > 0;
    }
    
    public static void main(String[] args) {
        Problem04_StoneGame sol = new Problem04_StoneGame();
        System.out.println(sol.stoneGame(new int[]{5,3,4,5})); // true
    }
}
