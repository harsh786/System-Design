import java.util.*;

public class Problem20_StoneGameV {
    // 1563. Stone Game V: Split row into two non-empty parts. Keep the smaller sum side (or either if equal).
    // Score = sum of kept side. Repeat until one stone. Maximize total score.
    
    public int stoneGameV(int[] stoneValue) {
        int n = stoneValue.length;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + stoneValue[i];
        int[][] dp = new int[n][n];
        for (int[] r : dp) Arrays.fill(r, -1);
        return solve(dp, prefix, 0, n - 1);
    }
    
    private int solve(int[][] dp, int[] prefix, int l, int r) {
        if (l == r) return 0;
        if (dp[l][r] != -1) return dp[l][r];
        int res = 0;
        for (int m = l; m < r; m++) {
            int left = prefix[m+1] - prefix[l];
            int right = prefix[r+1] - prefix[m+1];
            if (left <= right) res = Math.max(res, left + solve(dp, prefix, l, m));
            if (right <= left) res = Math.max(res, right + solve(dp, prefix, m+1, r));
        }
        dp[l][r] = res;
        return res;
    }
    
    public static void main(String[] args) {
        Problem20_StoneGameV sol = new Problem20_StoneGameV();
        System.out.println(sol.stoneGameV(new int[]{6,2,3,4,5,5})); // 18
    }
}
