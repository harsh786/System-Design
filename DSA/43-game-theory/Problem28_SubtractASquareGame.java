import java.util.*;

public class Problem28_SubtractASquareGame {
    // Subtract a Square: Two players subtract perfect squares from n. Who can't move loses.
    
    public boolean canFirstPlayerWin(int n) {
        boolean[] dp = new boolean[n + 1];
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j * j <= i; j++) {
                if (!dp[i - j * j]) { dp[i] = true; break; }
            }
        }
        return dp[n];
    }
    
    public static void main(String[] args) {
        Problem28_SubtractASquareGame sol = new Problem28_SubtractASquareGame();
        for (int i = 1; i <= 20; i++) {
            System.out.println("n=" + i + ": " + (sol.canFirstPlayerWin(i) ? "Win" : "Lose"));
        }
    }
}
