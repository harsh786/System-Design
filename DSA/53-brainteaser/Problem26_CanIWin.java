import java.util.*;

public class Problem26_CanIWin {
    // LC 464
    static Map<Integer, Boolean> memo = new HashMap<>();
    
    static boolean canIWin(int maxChoosable, int desiredTotal) {
        if (maxChoosable * (maxChoosable + 1) / 2 < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        return canWin(maxChoosable, desiredTotal, 0);
    }
    
    static boolean canWin(int max, int remaining, int used) {
        if (memo.containsKey(used)) return memo.get(used);
        for (int i = 1; i <= max; i++) {
            if ((used & (1 << i)) != 0) continue;
            if (i >= remaining || !canWin(max, remaining - i, used | (1 << i))) {
                memo.put(used, true); return true;
            }
        }
        memo.put(used, false); return false;
    }
    
    public static void main(String[] args) {
        System.out.println(canIWin(10, 11)); // false
        memo.clear();
        System.out.println(canIWin(10, 40)); // false
    }
}
