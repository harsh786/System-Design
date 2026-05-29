import java.util.*;

public class Problem32_StoneGame {
    private Integer[][] memo;

    public boolean stoneGame(int[] piles) {
        int n = piles.length;
        memo = new Integer[n][n];
        return helper(piles, 0, n - 1) > 0;
    }

    private int helper(int[] piles, int l, int r) {
        if (l > r) return 0;
        if (memo[l][r] != null) return memo[l][r];
        boolean aliceTurn = (r - l + 1) % 2 == 0;
        if (aliceTurn) memo[l][r] = Math.max(piles[l] + helper(piles, l+1, r), piles[r] + helper(piles, l, r-1));
        else memo[l][r] = Math.min(-piles[l] + helper(piles, l+1, r), -piles[r] + helper(piles, l, r-1));
        return memo[l][r];
    }

    public static void main(String[] args) {
        Problem32_StoneGame sol = new Problem32_StoneGame();
        System.out.println(sol.stoneGame(new int[]{5,3,4,5})); // true
    }
}
