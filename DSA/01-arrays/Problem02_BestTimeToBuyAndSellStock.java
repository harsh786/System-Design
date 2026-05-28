/**
 * Problem 2: Best Time to Buy and Sell Stock
 * Find max profit from one buy and one sell.
 * 
 * Production Analogy: Like monitoring min latency seen so far and tracking max improvement
 * from that baseline - useful in SLA monitoring dashboards.
 * 
 * Brute Force: O(n^2) - check all pairs
 * Optimal: O(n) time, O(1) space - track min price, max profit
 */
public class Problem02_BestTimeToBuyAndSellStock {

    public static int maxProfitBrute(int[] prices) {
        int max = 0;
        for (int i = 0; i < prices.length; i++)
            for (int j = i + 1; j < prices.length; j++)
                max = Math.max(max, prices[j] - prices[i]);
        return max;
    }

    public static int maxProfit(int[] prices) {
        int minPrice = Integer.MAX_VALUE, maxProfit = 0;
        for (int price : prices) {
            minPrice = Math.min(minPrice, price);
            maxProfit = Math.max(maxProfit, price - minPrice);
        }
        return maxProfit;
    }

    public static void main(String[] args) {
        System.out.println(maxProfit(new int[]{7,1,5,3,6,4})); // 5
        System.out.println(maxProfit(new int[]{7,6,4,3,1}));   // 0
        System.out.println(maxProfit(new int[]{1}));            // 0
        System.out.println(maxProfit(new int[]{2,4,1}));        // 2
    }
}
