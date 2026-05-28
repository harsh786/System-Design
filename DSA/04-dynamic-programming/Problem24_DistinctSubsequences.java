/**
 * Problem 24: Distinct Subsequences
 * 
 * Count distinct subsequences of s that equal t.
 * 
 * State: dp[i][j] = number of subsequences of s[0..i-1] that equal t[0..j-1]
 * Recurrence: dp[i][j] = dp[i-1][j] + (s[i-1]==t[j-1] ? dp[i-1][j-1] : 0)
 * 
 * Time: O(m*n), Space: O(n)
 */
public class Problem24_DistinctSubsequences {

    public static int numDistinct(String s, String t) {
        int m = s.length(), n = t.length();
        int[] dp = new int[n + 1];
        dp[0] = 1;
        for (int i = 1; i <= m; i++) {
            for (int j = n; j >= 1; j--) {
                if (s.charAt(i - 1) == t.charAt(j - 1)) dp[j] += dp[j - 1];
            }
        }
        return dp[n];
    }

    public static void main(String[] args) {
        System.out.println("=== Distinct Subsequences ===");
        System.out.println(numDistinct("rabbbit", "rabbit")); // 3
        System.out.println(numDistinct("babgbag", "bag")); // 5
    }
}
