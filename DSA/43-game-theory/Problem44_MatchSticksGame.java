import java.util.*;

public class Problem44_MatchSticksGame {
    // Match Sticks Game: n matchsticks. Players take 1,2, or 3. Last pick wins.
    // Extension: given a set of allowed moves, determine winner.
    
    public boolean canFirstPlayerWin(int n, int[] allowedMoves) {
        boolean[] dp = new boolean[n + 1];
        for (int i = 1; i <= n; i++) {
            for (int m : allowedMoves) {
                if (i >= m && !dp[i - m]) {
                    dp[i] = true;
                    break;
                }
            }
        }
        return dp[n];
    }
    
    public static void main(String[] args) {
        Problem44_MatchSticksGame sol = new Problem44_MatchSticksGame();
        System.out.println(sol.canFirstPlayerWin(10, new int[]{1,2,3})); // true (10%4!=0)
        System.out.println(sol.canFirstPlayerWin(8, new int[]{1,2,3}));  // false (8%4==0)
        System.out.println(sol.canFirstPlayerWin(7, new int[]{2,3,5})); // true
    }
}
