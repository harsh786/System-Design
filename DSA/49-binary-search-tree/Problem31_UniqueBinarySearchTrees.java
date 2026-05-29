public class Problem31_UniqueBinarySearchTrees {
    // LC 96: Count structurally unique BSTs with n nodes (Catalan number)
    public static int numTrees(int n) {
        int[] dp = new int[n + 1];
        dp[0] = dp[1] = 1;
        for (int i = 2; i <= n; i++)
            for (int j = 0; j < i; j++)
                dp[i] += dp[j] * dp[i - 1 - j];
        return dp[n];
    }

    public static void main(String[] args) {
        System.out.println(numTrees(3)); // 5
        System.out.println(numTrees(5)); // 42
    }
}
