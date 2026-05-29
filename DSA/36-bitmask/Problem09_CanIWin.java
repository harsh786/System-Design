import java.util.*;

public class Problem09_CanIWin {
    public boolean canIWin(int maxChoosableInteger, int desiredTotal) {
        if (maxChoosableInteger * (maxChoosableInteger + 1) / 2 < desiredTotal) return false;
        if (desiredTotal <= 0) return true;
        return dfs(maxChoosableInteger, desiredTotal, 0, new HashMap<>());
    }

    private boolean dfs(int max, int remain, int mask, Map<Integer, Boolean> memo) {
        if (memo.containsKey(mask)) return memo.get(mask);
        for (int i = 1; i <= max; i++) {
            if ((mask & (1 << i)) != 0) continue;
            if (i >= remain || !dfs(max, remain - i, mask | (1 << i), memo)) {
                memo.put(mask, true); return true;
            }
        }
        memo.put(mask, false); return false;
    }

    public static void main(String[] args) {
        System.out.println(new Problem09_CanIWin().canIWin(10, 11));
    }
}
