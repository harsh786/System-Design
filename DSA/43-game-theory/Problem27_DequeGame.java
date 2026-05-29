import java.util.*;

public class Problem27_DequeGame {
    // Deque Game: Two players take from front or back of a deque.
    // Each player wants to maximize their own score. Return scores of both players.
    
    public int[] dequeGame(int[] arr) {
        int n = arr.length;
        int total = 0;
        for (int x : arr) total += x;
        int[][] dp = new int[n][n]; // score diff for current player
        for (int i = 0; i < n; i++) dp[i][i] = arr[i];
        for (int len = 2; len <= n; len++)
            for (int i = 0; i <= n-len; i++) {
                int j = i+len-1;
                dp[i][j] = Math.max(arr[i] - dp[i+1][j], arr[j] - dp[i][j-1]);
            }
        int p1 = (total + dp[0][n-1]) / 2;
        int p2 = total - p1;
        return new int[]{p1, p2};
    }
    
    public static void main(String[] args) {
        Problem27_DequeGame sol = new Problem27_DequeGame();
        System.out.println(Arrays.toString(sol.dequeGame(new int[]{1,5,233,7}))); // [238, 8]
    }
}
