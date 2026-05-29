import java.util.Arrays;

public class Problem42_BitmaskDPForPalindromePartitioning {
    // Minimum palindrome partitioning using bitmask on cut positions
    public int minCut(String s) {
        int n = s.length();
        boolean[][] isPalin = new boolean[n][n];
        for (int i = n-1; i >= 0; i--) for (int j = i; j < n; j++)
            isPalin[i][j] = s.charAt(i) == s.charAt(j) && (j - i < 2 || isPalin[i+1][j-1]);
        int[] dp = new int[n];
        for (int i = 0; i < n; i++) {
            if (isPalin[0][i]) { dp[i] = 0; continue; }
            dp[i] = i;
            for (int j = 1; j <= i; j++) if (isPalin[j][i]) dp[i] = Math.min(dp[i], dp[j-1] + 1);
        }
        return dp[n-1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem42_BitmaskDPForPalindromePartitioning().minCut("aab")); // 1
    }
}
