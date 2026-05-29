public class Problem17_UniqueBinarySearchTrees {
    public int numTrees(int n) {
        long[] dp = new long[n + 1];
        dp[0] = dp[1] = 1;
        for (int i = 2; i <= n; i++)
            for (int j = 0; j < i; j++)
                dp[i] += dp[j] * dp[i - 1 - j];
        return (int) dp[n];
    }

    public static void main(String[] args) {
        System.out.println(new Problem17_UniqueBinarySearchTrees().numTrees(5)); // 42
    }
}
