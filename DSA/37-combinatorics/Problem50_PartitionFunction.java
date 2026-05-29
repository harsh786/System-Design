public class Problem50_PartitionFunction {
    // Number of ways to write n as sum of positive integers (order doesn't matter)
    public int partition(int n) {
        int[] dp = new int[n + 1];
        dp[0] = 1;
        for (int i = 1; i <= n; i++)
            for (int j = i; j <= n; j++)
                dp[j] += dp[j - i];
        return dp[n];
    }

    public static void main(String[] args) {
        Problem50_PartitionFunction sol = new Problem50_PartitionFunction();
        System.out.println(sol.partition(10)); // 42
        System.out.println(sol.partition(20)); // 627
    }
}
