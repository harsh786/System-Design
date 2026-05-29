import java.util.*;

public class Problem07_StoneGameIV {
    // 1510. Stone Game IV: n stones, remove perfect square number each turn.
    // Player who cannot move loses. Return true if Alice wins.
    
    public boolean winnerSquareGame(int n) {
        boolean[] dp = new boolean[n + 1];
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j * j <= i; j++) {
                if (!dp[i - j * j]) {
                    dp[i] = true;
                    break;
                }
            }
        }
        return dp[n];
    }
    
    public static void main(String[] args) {
        Problem07_StoneGameIV sol = new Problem07_StoneGameIV();
        System.out.println(sol.winnerSquareGame(1));  // true
        System.out.println(sol.winnerSquareGame(2));  // false
        System.out.println(sol.winnerSquareGame(4));  // true
    }
}
