public class Problem34_NumberOfWaysToFormTargetString {
    public int numWays(String[] words, String target) {
        long MOD = 1_000_000_007;
        int m = words[0].length(), n = target.length();
        int[][] freq = new int[m][26];
        for (String w : words) for (int i = 0; i < m; i++) freq[i][w.charAt(i) - 'a']++;
        long[] dp = new long[n + 1];
        dp[0] = 1;
        for (int i = 0; i < m; i++)
            for (int j = Math.min(n, i + 1); j >= 1; j--)
                dp[j] = (dp[j] + dp[j-1] * freq[i][target.charAt(j-1) - 'a']) % MOD;
        return (int) dp[n];
    }

    public static void main(String[] args) {
        System.out.println(new Problem34_NumberOfWaysToFormTargetString().numWays(new String[]{"acca","bbbb","caca"}, "aba"));
    }
}
