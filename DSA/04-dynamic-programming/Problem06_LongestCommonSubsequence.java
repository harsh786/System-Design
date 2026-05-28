/**
 * Problem 6: Longest Common Subsequence
 * 
 * State: dp[i][j] = LCS of text1[0..i-1] and text2[0..j-1]
 * Recurrence: if text1[i-1]==text2[j-1]: dp[i][j] = dp[i-1][j-1]+1
 *             else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])
 * 
 * Time: O(m*n), Space: O(m*n) or O(min(m,n)) optimized
 * 
 * Production Analogy: Like diff algorithms comparing two versions of a config file
 * to find the longest unchanged portion.
 */
public class Problem06_LongestCommonSubsequence {

    public static int lcs(String text1, String text2) {
        int m = text1.length(), n = text2.length();
        int[][] dp = new int[m + 1][n + 1];
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (text1.charAt(i - 1) == text2.charAt(j - 1))
                    dp[i][j] = dp[i - 1][j - 1] + 1;
                else
                    dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
        }
        return dp[m][n];
    }

    // Space optimized to O(n)
    public static int lcsOpt(String text1, String text2) {
        int m = text1.length(), n = text2.length();
        int[] prev = new int[n + 1], curr = new int[n + 1];
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (text1.charAt(i - 1) == text2.charAt(j - 1))
                    curr[j] = prev[j - 1] + 1;
                else
                    curr[j] = Math.max(prev[j], curr[j - 1]);
            }
            int[] tmp = prev; prev = curr; curr = tmp;
            java.util.Arrays.fill(curr, 0);
        }
        return prev[n];
    }

    public static void main(String[] args) {
        System.out.println("=== LCS ===");
        System.out.println(lcs("abcde", "ace")); // 3
        System.out.println(lcs("abc", "def")); // 0
        System.out.println(lcsOpt("abcde", "ace")); // 3
    }
}
