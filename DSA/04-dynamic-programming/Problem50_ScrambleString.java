/**
 * Problem 50: Scramble String
 * 
 * Given s1, determine if s2 is a scrambled string of s1.
 * A string can be scrambled by splitting into two non-empty parts and optionally swapping them,
 * then recursively scrambling each part.
 * 
 * State: dp[i][j][len] = s1 starting at i and s2 starting at j with length len are scrambles
 * Time: O(n^4), Space: O(n^3)
 */
public class Problem50_ScrambleString {

    public static boolean isScramble(String s1, String s2) {
        int n = s1.length();
        if (n != s2.length()) return false;
        if (s1.equals(s2)) return true;
        boolean[][][] dp = new boolean[n][n][n + 1];
        // Base case: length 1
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                dp[i][j][1] = s1.charAt(i) == s2.charAt(j);
        // Fill for increasing lengths
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                for (int j = 0; j <= n - len; j++) {
                    for (int k = 1; k < len; k++) {
                        // No swap: first k chars match first k, rest match rest
                        if (dp[i][j][k] && dp[i + k][j + k][len - k]) {
                            dp[i][j][len] = true;
                            break;
                        }
                        // Swap: first k of s1 match last k of s2 segment
                        if (dp[i][j + len - k][k] && dp[i + k][j][len - k]) {
                            dp[i][j][len] = true;
                            break;
                        }
                    }
                }
            }
        }
        return dp[0][0][n];
    }

    public static void main(String[] args) {
        System.out.println("=== Scramble String ===");
        System.out.println(isScramble("great", "rgeat")); // true
        System.out.println(isScramble("abcde", "caebd")); // false
        System.out.println(isScramble("a", "a")); // true
    }
}
