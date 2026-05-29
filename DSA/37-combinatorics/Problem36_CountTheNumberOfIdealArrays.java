public class Problem36_CountTheNumberOfIdealArrays {
    static final long MOD = 1_000_000_007;

    public int idealArrays(int n, int maxValue) {
        // For each value, count sequences where each element divides next
        // Use stars and bars: length of prime factorization chain distributed in n slots
        int maxLen = 14; // log2(maxValue)
        long[][] comb = new long[n + maxLen][maxLen + 1];
        for (int i = 0; i < comb.length; i++) { comb[i][0] = 1; for (int j = 1; j <= Math.min(i, maxLen); j++) comb[i][j] = (comb[i-1][j-1] + comb[i-1][j]) % MOD; }
        // dp[v][len] = number of strictly increasing divisor chains ending at v with length len
        int[][] dp = new int[maxValue + 1][maxLen + 1];
        for (int v = 1; v <= maxValue; v++) dp[v][1] = 1;
        for (int len = 1; len < maxLen; len++)
            for (int v = 1; v <= maxValue; v++)
                if (dp[v][len] > 0)
                    for (int mul = 2 * v; mul <= maxValue; mul += v)
                        dp[mul][len + 1] += dp[v][len];
        long result = 0;
        for (int v = 1; v <= maxValue; v++)
            for (int len = 1; len <= maxLen; len++)
                if (dp[v][len] > 0)
                    result = (result + (long)dp[v][len] * comb[n - 1][len - 1]) % MOD;
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem36_CountTheNumberOfIdealArrays().idealArrays(5, 9));
    }
}
