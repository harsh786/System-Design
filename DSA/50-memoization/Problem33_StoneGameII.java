import java.util.*;

public class Problem33_StoneGameII {
    private int[][] memo;
    private int[] suffix;

    public int stoneGameII(int[] piles) {
        int n = piles.length;
        memo = new int[n][n + 1];
        for (int[] row : memo) Arrays.fill(row, -1);
        suffix = new int[n + 1];
        for (int i = n - 1; i >= 0; i--) suffix[i] = suffix[i + 1] + piles[i];
        return helper(piles, 0, 1);
    }

    private int helper(int[] piles, int i, int m) {
        if (i >= piles.length) return 0;
        if (2 * m >= piles.length - i) return suffix[i];
        if (memo[i][m] != -1) return memo[i][m];
        int max = 0;
        for (int x = 1; x <= 2 * m; x++) {
            max = Math.max(max, suffix[i] - helper(piles, i + x, Math.max(m, x)));
        }
        memo[i][m] = max;
        return max;
    }

    public static void main(String[] args) {
        Problem33_StoneGameII sol = new Problem33_StoneGameII();
        System.out.println(sol.stoneGameII(new int[]{2,7,9,4,4})); // 10
    }
}
