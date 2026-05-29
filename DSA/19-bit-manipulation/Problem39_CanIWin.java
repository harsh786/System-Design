/**
 * Problem 39: Can I Win (Bitmask DP)
 * Two players pick from 1..maxChoosableInteger (no reuse). First to reach desiredTotal wins.
 * 
 * Approach: Bitmask represents used numbers. Memoize on mask.
 * Time: O(2^n * n), Space: O(2^n)
 * 
 * Production Analogy: Game theory in resource bidding systems.
 */
import java.util.*;

public class Problem39_CanIWin {
    public static boolean canIWin(int maxChoosable, int desiredTotal) {
        if (maxChoosable * (maxChoosable + 1) / 2 < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        return dfs(maxChoosable, desiredTotal, 0, new HashMap<>());
    }

    private static boolean dfs(int max, int remain, int mask, Map<Integer, Boolean> memo) {
        if (memo.containsKey(mask)) return memo.get(mask);
        for (int i = 1; i <= max; i++) {
            if ((mask & (1 << i)) != 0) continue;
            if (i >= remain || !dfs(max, remain - i, mask | (1 << i), memo)) {
                memo.put(mask, true);
                return true;
            }
        }
        memo.put(mask, false);
        return false;
    }

    public static void main(String[] args) {
        System.out.println(canIWin(10, 11)); // false
        System.out.println(canIWin(10, 0)); // true
        System.out.println(canIWin(10, 1)); // true
    }
}
