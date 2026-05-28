/**
 * Problem 17: Longest Palindromic Subsequence
 * 
 * State: dp[i][j] = length of longest palindromic subsequence in s[i..j]
 * Recurrence: if s[i]==s[j]: dp[i][j] = dp[i+1][j-1] + 2
 *             else: dp[i][j] = max(dp[i+1][j], dp[i][j-1])
 * 
 * Time: O(n^2), Space: O(n^2)
 */
public class Problem17_LongestPalindromicSubsequence {

    public static int longestPalinSubseq(String s) {
        int n = s.length();
        int[][] dp = new int[n][n];
        for (int i = n - 1; i >= 0; i--) {
            dp[i][i] = 1;
            for (int j = i + 1; j < n; j++) {
                if (s.charAt(i) == s.charAt(j))
                    dp[i][j] = dp[i + 1][j - 1] + 2;
                else
                    dp[i][j] = Math.max(dp[i + 1][j], dp[i][j - 1]);
            }
        }
        return dp[0][n - 1];
    }

    public static void main(String[] args) {
        System.out.println("=== Longest Palindromic Subsequence ===");
        System.out.println(longestPalinSubseq("bbbab")); // 4
        System.out.println(longestPalinSubseq("cbbd")); // 2
    }
}
