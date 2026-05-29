import java.util.*;

public class Problem42_StrangePrinter {
    private Integer[][] memo;

    public int strangePrinter(String s) {
        int n = s.length();
        memo = new Integer[n][n];
        return helper(s, 0, n - 1);
    }

    private int helper(String s, int l, int r) {
        if (l > r) return 0;
        if (memo[l][r] != null) return memo[l][r];
        int result = helper(s, l + 1, r) + 1;
        for (int k = l + 1; k <= r; k++) {
            if (s.charAt(k) == s.charAt(l)) result = Math.min(result, helper(s, l + 1, k) + helper(s, k + 1, r));
        }
        memo[l][r] = result;
        return result;
    }

    public static void main(String[] args) {
        Problem42_StrangePrinter sol = new Problem42_StrangePrinter();
        System.out.println(sol.strangePrinter("aaabbb")); // 2
    }
}
