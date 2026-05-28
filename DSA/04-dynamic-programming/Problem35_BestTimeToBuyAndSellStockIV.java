/**
 * Problem 35: Best Time to Buy and Sell Stock IV
 * 
 * At most k transactions.
 * 
 * State: dp[t][i] = max profit using at most t transactions up to day i
 * Optimization: if k >= n/2, unlimited transactions.
 * 
 * Time: O(n*k), Space: O(k)
 */
public class Problem35_BestTimeToBuyAndSellStockIV {

    public static int maxProfit(int k, int[] prices) {
        int n = prices.length;
        if (n < 2) return 0;
        if (k >= n / 2) {
            int profit = 0;
            for (int i = 1; i < n; i++) profit += Math.max(0, prices[i] - prices[i - 1]);
            return profit;
        }
        int[] buy = new int[k + 1], sell = new int[k + 1];
        java.util.Arrays.fill(buy, Integer.MIN_VALUE);
        for (int p : prices) {
            for (int t = 1; t <= k; t++) {
                buy[t] = Math.max(buy[t], sell[t - 1] - p);
                sell[t] = Math.max(sell[t], buy[t] + p);
            }
        }
        return sell[k];
    }

    public static void main(String[] args) {
        System.out.println("=== Stock IV ===");
        System.out.println(maxProfit(2, new int[]{2,4,1})); // 2
        System.out.println(maxProfit(2, new int[]{3,2,6,5,0,3})); // 7
    }
}
