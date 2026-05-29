import java.util.*;

public class Problem02_CanIWin {
    // 464. Can I Win: Two players take turns picking from 1..maxChoosableInteger (no reuse).
    // The player whose running total >= desiredTotal wins. Can the first player force a win?
    
    public boolean canIWin(int maxChoosableInteger, int desiredTotal) {
        int sum = maxChoosableInteger * (maxChoosableInteger + 1) / 2;
        if (sum < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        Map<Integer, Boolean> memo = new HashMap<>();
        return canWin(0, desiredTotal, maxChoosableInteger, memo);
    }
    
    private boolean canWin(int used, int remaining, int max, Map<Integer, Boolean> memo) {
        if (memo.containsKey(used)) return memo.get(used);
        for (int i = 1; i <= max; i++) {
            if ((used & (1 << i)) != 0) continue;
            if (i >= remaining || !canWin(used | (1 << i), remaining - i, max, memo)) {
                memo.put(used, true);
                return true;
            }
        }
        memo.put(used, false);
        return false;
    }
    
    public static void main(String[] args) {
        Problem02_CanIWin sol = new Problem02_CanIWin();
        System.out.println(sol.canIWin(10, 11)); // false
        System.out.println(sol.canIWin(10, 0));  // true
        System.out.println(sol.canIWin(10, 40)); // false
    }
}
