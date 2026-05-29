import java.util.*;

public class Problem13_CanIWin {
    private Map<Integer, Boolean> memo = new HashMap<>();

    public boolean canIWin(int maxChoosableInteger, int desiredTotal) {
        if (maxChoosableInteger * (maxChoosableInteger + 1) / 2 < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        return helper(maxChoosableInteger, desiredTotal, 0);
    }

    private boolean helper(int max, int remaining, int used) {
        if (memo.containsKey(used)) return memo.get(used);
        for (int i = 1; i <= max; i++) {
            if ((used & (1 << i)) != 0) continue;
            if (i >= remaining || !helper(max, remaining - i, used | (1 << i))) {
                memo.put(used, true);
                return true;
            }
        }
        memo.put(used, false);
        return false;
    }

    public static void main(String[] args) {
        Problem13_CanIWin sol = new Problem13_CanIWin();
        System.out.println("canIWin(10,11): " + sol.canIWin(10, 11)); // false
    }
}
