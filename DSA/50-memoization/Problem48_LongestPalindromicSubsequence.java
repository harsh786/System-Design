import java.util.*;

public class Problem48_LongestPalindromicSubsequence {
    private Integer[][] memo;

    public int longestPalinSubseq(String s) {
        memo = new Integer[s.length()][s.length()];
        return helper(s, 0, s.length() - 1);
    }

    private int helper(String s, int l, int r) {
        if (l > r) return 0;
        if (l == r) return 1;
        if (memo[l][r] != null) return memo[l][r];
        if (s.charAt(l) == s.charAt(r)) memo[l][r] = 2 + helper(s, l + 1, r - 1);
        else memo[l][r] = Math.max(helper(s, l + 1, r), helper(s, l, r - 1));
        return memo[l][r];
    }

    public static void main(String[] args) {
        Problem48_LongestPalindromicSubsequence sol = new Problem48_LongestPalindromicSubsequence();
        System.out.println(sol.longestPalinSubseq("bbbab")); // 4
    }
}
