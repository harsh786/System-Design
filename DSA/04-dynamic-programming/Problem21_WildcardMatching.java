/**
 * Problem 21: Wildcard Matching
 * 
 * '?' matches any single char, '*' matches any sequence (including empty).
 * 
 * State: dp[i][j] = s[0..i-1] matches p[0..j-1]
 * Time: O(m*n), Space: O(m*n)
 */
public class Problem21_WildcardMatching {

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
                if (pc == '?' || pc == s.charAt(i - 1)) {
                    dp[i][j] = dp[i - 1][j - 1];
                } else if (pc == '*') {
                    dp[i][j] = dp[i][j - 1] || dp[i - 1][j];
                }
            }
        }
        return dp[m][n];
    }

    public static void main(String[] args) {
        System.out.println("=== Wildcard Matching ===");
        System.out.println(isMatch("aa", "a")); // false
        System.out.println(isMatch("aa", "*")); // true
        System.out.println(isMatch("cb", "?a")); // false
        System.out.println(isMatch("adceb", "*a*b")); // true
    }
}
