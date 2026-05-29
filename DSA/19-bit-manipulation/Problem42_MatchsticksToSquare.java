/**
 * Problem 42: Matchsticks to Square (Bitmask)
 * Can matchsticks form a perfect square (4 equal sides)?
 * 
 * Approach: Bitmask DP. Find subsets summing to side, then partition into 4 such subsets.
 * Or use backtracking with bitmask memoization.
 * Time: O(n * 2^n), Space: O(2^n)
 * 
 * Production Analogy: Balanced load distribution across 4 data centers.
 */
import java.util.*;

public class Problem42_MatchsticksToSquare {
    public static boolean makesquare(int[] matchsticks) {
        int sum = Arrays.stream(matchsticks).sum();
        if (sum % 4 != 0) return false;
        int side = sum / 4, n = matchsticks.length;
        // dp[mask] = remaining space in current side being filled, -1 if invalid
        int[] dp = new int[1 << n];
        Arrays.fill(dp, -1);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == -1) continue;
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                if (dp[mask] + matchsticks[i] <= side) {
                    int newMask = mask | (1 << i);
                    dp[newMask] = (dp[mask] + matchsticks[i]) % side;
                }
            }
        }
        return dp[(1 << n) - 1] == 0;
    }

    public static void main(String[] args) {
        System.out.println(makesquare(new int[]{1,1,2,2,2})); // true
        System.out.println(makesquare(new int[]{3,3,3,3,4})); // false
    }
}
