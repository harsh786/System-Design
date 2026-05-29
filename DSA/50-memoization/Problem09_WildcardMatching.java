import java.util.*;

public class Problem09_WildcardMatching {
    private Boolean[][] memo;

    public boolean isMatch(String s, String p) {
        memo = new Boolean[s.length() + 1][p.length() + 1];
        return helper(s, p, 0, 0);
    }

    private boolean helper(String s, String p, int i, int j) {
        if (j == p.length()) return i == s.length();
        if (memo[i][j] != null) return memo[i][j];
        boolean result;
        if (p.charAt(j) == '*') {
            result = helper(s, p, i, j + 1) || (i < s.length() && helper(s, p, i + 1, j));
        } else {
            result = i < s.length() && (s.charAt(i) == p.charAt(j) || p.charAt(j) == '?') && helper(s, p, i + 1, j + 1);
        }
        memo[i][j] = result;
        return result;
    }

    public static void main(String[] args) {
        Problem09_WildcardMatching sol = new Problem09_WildcardMatching();
        System.out.println("isMatch('adceb','*a*b'): " + sol.isMatch("adceb", "*a*b")); // true
    }
}
