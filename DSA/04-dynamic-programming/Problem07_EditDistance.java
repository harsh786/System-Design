/**
 * Problem 7: Edit Distance (Levenshtein Distance)
 * 
 * State: dp[i][j] = min operations to convert word1[0..i-1] to word2[0..j-1]
 * Recurrence: if match: dp[i][j] = dp[i-1][j-1]
 *             else: dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
 * 
 * Time: O(m*n), Space: O(m*n)
 * 
 * Production Analogy: Like computing the cost of migrating one database schema to another,
 * where each add/remove/modify column has unit cost.
 */
public class Problem07_EditDistance {

    public static int minDistance(String word1, String word2) {
        int m = word1.length(), n = word2.length();
        int[][] dp = new int[m + 1][n + 1];
        for (int i = 0; i <= m; i++) dp[i][0] = i;
        for (int j = 0; j <= n; j++) dp[0][j] = j;
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (word1.charAt(i - 1) == word2.charAt(j - 1))
                    dp[i][j] = dp[i - 1][j - 1];
                else
                    dp[i][j] = 1 + Math.min(dp[i - 1][j - 1], Math.min(dp[i - 1][j], dp[i][j - 1]));
            }
        }
        return dp[m][n];
    }

    public static void main(String[] args) {
        System.out.println("=== Edit Distance ===");
        System.out.println(minDistance("horse", "ros")); // 3
        System.out.println(minDistance("intention", "execution")); // 5
        System.out.println(minDistance("", "abc")); // 3
        System.out.println(minDistance("abc", "abc")); // 0
    }
}
