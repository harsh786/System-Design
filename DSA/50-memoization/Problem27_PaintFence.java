import java.util.*;

public class Problem27_PaintFence {
    private Map<String, Integer> memo = new HashMap<>();

    public int numWays(int n, int k) {
        if (n == 0) return 0;
        if (n == 1) return k;
        return helper(n, k, -1, -1);
    }

    private int helper(int remaining, int k, int last, int secondLast) {
        if (remaining == 0) return 1;
        String key = remaining + "," + last + "," + secondLast;
        if (memo.containsKey(key)) return memo.get(key);
        int ways = 0;
        for (int c = 0; c < k; c++) {
            if (c == last && c == secondLast) continue;
            ways += helper(remaining - 1, k, c, last);
        }
        memo.put(key, ways);
        return ways;
    }

    // Simpler O(n) approach with memo
    public int numWaysSimple(int n, int k) {
        if (n == 0) return 0;
        if (n == 1) return k;
        int same = k, diff = k * (k - 1);
        for (int i = 3; i <= n; i++) {
            int prevDiff = diff;
            diff = (same + diff) * (k - 1);
            same = prevDiff;
        }
        return same + diff;
    }

    public static void main(String[] args) {
        Problem27_PaintFence sol = new Problem27_PaintFence();
        System.out.println("Paint fence n=3,k=2: " + sol.numWaysSimple(3, 2)); // 6
    }
}
