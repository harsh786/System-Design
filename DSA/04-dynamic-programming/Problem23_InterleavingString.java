/**
 * Problem 23: Interleaving String
 * 
 * Given s1, s2, s3, check if s3 is formed by interleaving s1 and s2.
 * 
 * State: dp[i][j] = s1[0..i-1] and s2[0..j-1] can form s3[0..i+j-1]
 * Time: O(m*n), Space: O(n)
 */
public class Problem23_InterleavingString {

    public static boolean isInterleave(String s1, String s2, String s3) {
        int m = s1.length(), n = s2.length();
        if (m + n != s3.length()) return false;
        boolean[] dp = new boolean[n + 1];
        for (int i = 0; i <= m; i++) {
            for (int j = 0; j <= n; j++) {
                if (i == 0 && j == 0) { dp[j] = true; }
                else if (i == 0) { dp[j] = dp[j - 1] && s2.charAt(j - 1) == s3.charAt(j - 1); }
                else if (j == 0) { dp[j] = dp[j] && s1.charAt(i - 1) == s3.charAt(i - 1); }
                else {
                    dp[j] = (dp[j] && s1.charAt(i - 1) == s3.charAt(i + j - 1)) ||
                            (dp[j - 1] && s2.charAt(j - 1) == s3.charAt(i + j - 1));
                }
            }
        }
        return dp[n];
    }

    public static void main(String[] args) {
        System.out.println("=== Interleaving String ===");
        System.out.println(isInterleave("aabcc", "dbbca", "aadbbcbcac")); // true
        System.out.println(isInterleave("aabcc", "dbbca", "aadbbbaccc")); // false
        System.out.println(isInterleave("", "", "")); // true
    }
}
