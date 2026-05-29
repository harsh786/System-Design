import java.util.*;

public class Problem49_PatternMatchingWithWildcardsSA {
    // Pattern matching with '?' wildcard (matches any single char)
    public static List<Integer> matchWithWildcard(String text, String pattern) {
        List<Integer> result = new ArrayList<>();
        int n = text.length(), m = pattern.length();
        for (int i = 0; i <= n - m; i++) {
            boolean match = true;
            for (int j = 0; j < m; j++) {
                if (pattern.charAt(j) != '?' && pattern.charAt(j) != text.charAt(i+j)) {
                    match = false; break;
                }
            }
            if (match) result.add(i);
        }
        return result;
    }

    // For '*' wildcard: split pattern by '*', search each part with SA
    public static boolean matchWithStar(String text, String pattern) {
        // Simple DP approach
        int n = text.length(), m = pattern.length();
        boolean[][] dp = new boolean[n+1][m+1];
        dp[0][0] = true;
        for (int j = 1; j <= m; j++) if (pattern.charAt(j-1)=='*') dp[0][j] = dp[0][j-1];
        for (int i = 1; i <= n; i++)
            for (int j = 1; j <= m; j++) {
                if (pattern.charAt(j-1)=='*') dp[i][j] = dp[i-1][j] || dp[i][j-1];
                else if (pattern.charAt(j-1)=='?' || pattern.charAt(j-1)==text.charAt(i-1)) dp[i][j] = dp[i-1][j-1];
            }
        return dp[n][m];
    }

    public static void main(String[] args) {
        System.out.println(matchWithWildcard("abcabc", "a?c")); // [0,3]
        System.out.println(matchWithStar("abcdefg", "a*d*g")); // true
        System.out.println(matchWithStar("abcdefg", "a*x*g")); // false
    }
}
