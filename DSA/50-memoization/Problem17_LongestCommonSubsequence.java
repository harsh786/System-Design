import java.util.*;

public class Problem17_LongestCommonSubsequence {
    private Integer[][] memo;

    public int longestCommonSubsequence(String text1, String text2) {
        memo = new Integer[text1.length()][text2.length()];
        return helper(text1, text2, 0, 0);
    }

    private int helper(String t1, String t2, int i, int j) {
        if (i == t1.length() || j == t2.length()) return 0;
        if (memo[i][j] != null) return memo[i][j];
        if (t1.charAt(i) == t2.charAt(j)) memo[i][j] = 1 + helper(t1, t2, i + 1, j + 1);
        else memo[i][j] = Math.max(helper(t1, t2, i + 1, j), helper(t1, t2, i, j + 1));
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem17_LongestCommonSubsequence sol = new Problem17_LongestCommonSubsequence();
        System.out.println("LCS 'abcde','ace': " + sol.longestCommonSubsequence("abcde", "ace")); // 3
    }
}
