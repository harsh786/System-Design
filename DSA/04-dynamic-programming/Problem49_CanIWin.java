/**
 * Problem 49: Can I Win
 * 
 * Players take turns picking from 1..maxChoosableInteger (no reuse).
 * First to reach desiredTotal wins. Can first player force a win?
 * 
 * State: bitmask of used numbers -> can current player win?
 * Time: O(2^n * n), Space: O(2^n)
 */
import java.util.*;

public class Problem49_CanIWin {

    public static boolean canIWin(int maxChoosableInteger, int desiredTotal) {
        int sum = maxChoosableInteger * (maxChoosableInteger + 1) / 2;
        if (sum < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        Map<Integer, Boolean> memo = new HashMap<>();
        return dfs(maxChoosableInteger, desiredTotal, 0, memo);
    }

    private static boolean dfs(int max, int remaining, int used, Map<Integer, Boolean> memo) {
        if (memo.containsKey(used)) return memo.get(used);
        for (int i = 1; i <= max; i++) {
            if ((used & (1 << i)) != 0) continue;
            if (i >= remaining || !dfs(max, remaining - i, used | (1 << i), memo)) {
                memo.put(used, true);
                return true;
            }
        }
        memo.put(used, false);
        return false;
    }

    public static void main(String[] args) {
        System.out.println("=== Can I Win ===");
        System.out.println(canIWin(10, 11)); // false
        System.out.println(canIWin(10, 0)); // true
        System.out.println(canIWin(10, 1)); // true
    }
}
