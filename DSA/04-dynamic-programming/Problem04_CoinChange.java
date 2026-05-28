/**
 * Problem 4: Coin Change
 * 
 * Given coins of different denominations and a total amount, find the fewest
 * number of coins needed to make up that amount. Return -1 if not possible.
 * 
 * State: dp[i] = minimum coins to make amount i
 * Recurrence: dp[i] = min(dp[i - coin] + 1) for each coin where coin <= i
 * Base: dp[0] = 0
 * 
 * Time: O(amount * coins), Space: O(amount)
 * 
 * Production Analogy: Like minimizing the number of API calls/microservice hops
 * needed to fulfill a request of a given size using different batch sizes.
 */
public class Problem04_CoinChange {

    // Top-down
    public static int coinChangeMemo(int[] coins, int amount) {
        int[] memo = new int[amount + 1];
        java.util.Arrays.fill(memo, -2);
        int res = helper(coins, amount, memo);
        return res;
    }

    private static int helper(int[] coins, int amount, int[] memo) {
        if (amount == 0) return 0;
        if (amount < 0) return -1;
        if (memo[amount] != -2) return memo[amount];
        int min = Integer.MAX_VALUE;
        for (int coin : coins) {
            int sub = helper(coins, amount - coin, memo);
            if (sub >= 0) min = Math.min(min, sub + 1);
        }
        memo[amount] = (min == Integer.MAX_VALUE) ? -1 : min;
        return memo[amount];
    }

    // Bottom-up
    public static int coinChangeTab(int[] coins, int amount) {
        int[] dp = new int[amount + 1];
        java.util.Arrays.fill(dp, amount + 1);
        dp[0] = 0;
        for (int i = 1; i <= amount; i++) {
            for (int coin : coins) {
                if (coin <= i) dp[i] = Math.min(dp[i], dp[i - coin] + 1);
            }
        }
        return dp[amount] > amount ? -1 : dp[amount];
    }

    public static void main(String[] args) {
        System.out.println("=== Coin Change ===");
        System.out.println(coinChangeTab(new int[]{1,5,10,25}, 30)); // 2
        System.out.println(coinChangeTab(new int[]{2}, 3)); // -1
        System.out.println(coinChangeMemo(new int[]{1,2,5}, 11)); // 3
        System.out.println(coinChangeTab(new int[]{1}, 0)); // 0
    }
}
