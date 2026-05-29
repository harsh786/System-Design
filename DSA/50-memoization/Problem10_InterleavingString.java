import java.util.*;

public class Problem10_InterleavingString {
    private Boolean[][] memo;

    public boolean isInterleave(String s1, String s2, String s3) {
        if (s1.length() + s2.length() != s3.length()) return false;
        memo = new Boolean[s1.length() + 1][s2.length() + 1];
        return helper(s1, s2, s3, 0, 0);
    }

    private boolean helper(String s1, String s2, String s3, int i, int j) {
        if (i + j == s3.length()) return true;
        if (memo[i][j] != null) return memo[i][j];
        boolean result = false;
        if (i < s1.length() && s1.charAt(i) == s3.charAt(i + j)) result = helper(s1, s2, s3, i + 1, j);
        if (!result && j < s2.length() && s2.charAt(j) == s3.charAt(i + j)) result = helper(s1, s2, s3, i, j + 1);
        memo[i][j] = result;
        return result;
    }

    public static void main(String[] args) {
        Problem10_InterleavingString sol = new Problem10_InterleavingString();
        System.out.println(sol.isInterleave("aabcc", "dbbca", "aadbbcbcac")); // true
    }
}
