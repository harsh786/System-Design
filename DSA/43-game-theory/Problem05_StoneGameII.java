import java.util.*;

public class Problem05_StoneGameII {
    // 1140. Stone Game II: Piles in a row. On each turn, take first 1..2M piles. M = max(M, X).
    // Return max stones first player (Alice) can get.
    
    public int stoneGameII(int[] piles) {
        int n = piles.length;
        int[] suffix = new int[n + 1];
        for (int i = n - 1; i >= 0; i--) suffix[i] = suffix[i+1] + piles[i];
        int[][] dp = new int[n][n + 1]; // dp[i][m] = max stones current player from index i with M=m
        for (int[][] row : new int[][][]{dp}) for (int[] r : row) Arrays.fill(r, -1);
        return dfs(piles, suffix, dp, 0, 1);
    }
    
    private int dfs(int[] piles, int[] suffix, int[][] dp, int i, int m) {
        int n = piles.length;
        if (i >= n) return 0;
        if (2 * m >= n - i) return suffix[i];
        if (dp[i][m] != -1) return dp[i][m];
        int best = 0;
        for (int x = 1; x <= 2 * m; x++) {
            best = Math.max(best, suffix[i] - dfs(piles, suffix, dp, i + x, Math.max(m, x)));
        }
        dp[i][m] = best;
        return best;
    }
    
    public static void main(String[] args) {
        Problem05_StoneGameII sol = new Problem05_StoneGameII();
        System.out.println(sol.stoneGameII(new int[]{2,7,9,4,4})); // 10
    }
}
