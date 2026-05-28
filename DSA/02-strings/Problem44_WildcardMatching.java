import java.util.*;

/**
 * Problem 44: Wildcard Matching (LeetCode 44)
 * 
 * '?' matches any single char, '*' matches any sequence (including empty).
 * Approach: 2D DP. O(m*n) time, O(m*n) space.
 * 
 * Production Analogy: Like glob pattern matching in file systems (ls *.txt).
 */
public class Problem44_WildcardMatching {

    public static boolean isMatch(String s, String p) {
        int m = s.length(), n = p.length();
        boolean[][] dp = new boolean[m + 1][n + 1];
        dp[0][0] = true;
        for (int j = 1; j <= n; j++) {
            if (p.charAt(j - 1) == '*') dp[0][j] = dp[0][j - 1];
        }
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                char pc = p.charAt(j - 1);
                if (pc == '?' || pc == s.charAt(i - 1)) dp[i][j] = dp[i-1][j-1];
                else if (pc == '*') dp[i][j] = dp[i-1][j] || dp[i][j-1];
            }
        }
        return dp[m][n];
    }

    public static void main(String[] args) {
        System.out.println(isMatch("aa", "a"));    // false
        System.out.println(isMatch("aa", "*"));    // true
        System.out.println(isMatch("cb", "?a"));   // false
        System.out.println(isMatch("adceb", "*a*b")); // true
    }
}
