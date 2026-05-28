/**
 * Problem 46: Stone Game II
 * 
 * Players take turns. On each turn, take first X piles where 1 <= X <= 2M.
 * M starts at 1, updated to max(M, X) after each turn.
 * 
 * State: dp[i][m] = max stones current player can get from piles[i:] with given M
 * Time: O(n^2 * n), Space: O(n^2)
 */
public class Problem46_StoneGameII {

    public static int stoneGameII(int[] piles) {
        int n = piles.length;
        int[] suffix = new int[n + 1];
        for (int i = n - 1; i >= 0; i--) suffix[i] = suffix[i + 1] + piles[i];
        int[][] dp = new int[n][n + 1];
        for (int i = n - 1; i >= 0; i--) {
            for (int m = 1; m <= n; m++) {
                if (i + 2 * m >= n) {
                    dp[i][m] = suffix[i];
                } else {
                    for (int x = 1; x <= 2 * m; x++) {
                        dp[i][m] = Math.max(dp[i][m], suffix[i] - dp[i + x][Math.max(m, x)]);
                    }
                }
            }
        }
        return dp[0][1];
    }

    public static void main(String[] args) {
        System.out.println("=== Stone Game II ===");
        System.out.println(stoneGameII(new int[]{2,7,9,4,4})); // 10
        System.out.println(stoneGameII(new int[]{1,2,3,4,5,100})); // 104
    }
}
