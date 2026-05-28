import java.util.*;

/**
 * Problem 41: Longest Common Subsequence (LeetCode 1143)
 * 
 * Approach: 2D DP. dp[i][j] = LCS of text1[0..i) and text2[0..j).
 * O(m*n) time, O(m*n) space (can optimize to O(min(m,n))).
 * 
 * Production Analogy: Like computing diff between two file versions (git diff uses LCS).
 */
public class Problem41_LongestCommonSubsequence {

    public static int longestCommonSubsequence(String text1, String text2) {
        int m = text1.length(), n = text2.length();
        int[][] dp = new int[m + 1][n + 1];
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (text1.charAt(i - 1) == text2.charAt(j - 1)) dp[i][j] = dp[i-1][j-1] + 1;
                else dp[i][j] = Math.max(dp[i-1][j], dp[i][j-1]);
            }
        }
        return dp[m][n];
    }

    public static void main(String[] args) {
        System.out.println(longestCommonSubsequence("abcde", "ace")); // 3
        System.out.println(longestCommonSubsequence("abc", "abc"));   // 3
        System.out.println(longestCommonSubsequence("abc", "def"));   // 0
    }
}
