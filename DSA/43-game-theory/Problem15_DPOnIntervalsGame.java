import java.util.*;

public class Problem15_DPOnIntervalsGame {
    // DP on Intervals Game: Burst balloons style interval DP game.
    // Two players alternately remove elements; score depends on interval choices.
    // Example: maximize score difference in interval picking game.
    
    public int intervalGame(int[] arr) {
        int n = arr.length;
        // dp[i][j] = max score diff current player can achieve on arr[i..j]
        int[][] dp = new int[n][n];
        for (int i = 0; i < n; i++) dp[i][i] = arr[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                dp[i][j] = Math.max(arr[i] - dp[i+1][j], arr[j] - dp[i][j-1]);
            }
        }
        return dp[0][n-1];
    }
    
    public static void main(String[] args) {
        Problem15_DPOnIntervalsGame sol = new Problem15_DPOnIntervalsGame();
        System.out.println(sol.intervalGame(new int[]{3,9,1,2})); // 7
    }
}
