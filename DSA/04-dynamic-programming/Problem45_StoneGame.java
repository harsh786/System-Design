/**
 * Problem 45: Stone Game
 * 
 * Alex and Lee pick from either end. Alex goes first. Does Alex always win?
 * (For even-length with odd total, Alex always wins - math proof)
 * 
 * DP approach: dp[i][j] = max score difference the current player can achieve from piles[i..j]
 * Time: O(n^2), Space: O(n^2)
 */
public class Problem45_StoneGame {

    public static boolean stoneGame(int[] piles) {
        int n = piles.length;
        int[][] dp = new int[n][n];
        for (int i = 0; i < n; i++) dp[i][i] = piles[i];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i + len - 1 < n; i++) {
                int j = i + len - 1;
                dp[i][j] = Math.max(piles[i] - dp[i + 1][j], piles[j] - dp[i][j - 1]);
            }
        }
        return dp[0][n - 1] > 0;
    }

    public static void main(String[] args) {
        System.out.println("=== Stone Game ===");
        System.out.println(stoneGame(new int[]{5,3,4,5})); // true
        System.out.println(stoneGame(new int[]{3,7,2,3})); // true
    }
}
