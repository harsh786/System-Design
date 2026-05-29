import java.util.*;

public class Problem08_DivisorGame {
    // 1025. Divisor Game: Number n on board. Pick x where 0 < x < n and n%x==0.
    // Replace n with n-x. Player who can't move loses. Alice goes first.
    // Key insight: Alice wins iff n is even.
    
    public boolean divisorGame(int n) {
        return n % 2 == 0;
    }
    
    // DP verification
    public boolean divisorGameDP(int n) {
        boolean[] dp = new boolean[n + 1];
        for (int i = 2; i <= n; i++) {
            for (int x = 1; x < i; x++) {
                if (i % x == 0 && !dp[i - x]) {
                    dp[i] = true;
                    break;
                }
            }
        }
        return dp[n];
    }
    
    public static void main(String[] args) {
        Problem08_DivisorGame sol = new Problem08_DivisorGame();
        System.out.println(sol.divisorGame(2));  // true
        System.out.println(sol.divisorGame(3));  // false
        System.out.println(sol.divisorGameDP(6)); // true
    }
}
