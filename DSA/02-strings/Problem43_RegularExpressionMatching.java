import java.util.*;

/**
 * Problem 43: Regular Expression Matching (LeetCode 10)
 * 
 * Implement regex with '.' (any char) and '*' (zero or more of preceding).
 * Approach: 2D DP. dp[i][j] = does s[0..i) match p[0..j)?
 * O(m*n) time, O(m*n) space.
 * 
 * Production Analogy: Like implementing a simplified regex engine for log pattern matching.
 */
public class Problem43_RegularExpressionMatching {

    public static boolean isMatch(String s, String p) {
        int m = s.length(), n = p.length();
        boolean[][] dp = new boolean[m + 1][n + 1];
        dp[0][0] = true;
        // Handle patterns like a*, a*b*, etc. matching empty string
        for (int j = 2; j <= n; j++) {
            if (p.charAt(j - 1) == '*') dp[0][j] = dp[0][j - 2];
        }
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                char pc = p.charAt(j - 1), sc = s.charAt(i - 1);
                if (pc == '.' || pc == sc) {
                    dp[i][j] = dp[i-1][j-1];
                } else if (pc == '*') {
                    char prev = p.charAt(j - 2);
                    dp[i][j] = dp[i][j-2]; // zero occurrences
                    if (prev == '.' || prev == sc) dp[i][j] |= dp[i-1][j]; // one+ occurrences
                }
            }
        }
        return dp[m][n];
    }

    public static void main(String[] args) {
        System.out.println(isMatch("aa", "a"));    // false
        System.out.println(isMatch("aa", "a*"));   // true
        System.out.println(isMatch("ab", ".*"));   // true
        System.out.println(isMatch("aab", "c*a*b")); // true
        System.out.println(isMatch("mississippi", "mis*is*p*.")); // false
    }
}
