/**
 * Problem 13: Best Time to Buy and Sell Stock II (LeetCode 122)
 *
 * Greedy Choice: Collect every positive price difference (buy every valley, sell every peak).
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Spot instance pricing - buy compute when cheap, release when expensive.
 */
public class Problem13_BestTimeToBuyAndSellStockII {
    
    public static int maxProfit(int[] prices) {
        int profit = 0;
        for (int i = 1; i < prices.length; i++)
            if (prices[i] > prices[i-1]) profit += prices[i] - prices[i-1];
        return profit;
    }
    
    public static void main(String[] args) {
        System.out.println(maxProfit(new int[]{7,1,5,3,6,4})); // 7
        System.out.println(maxProfit(new int[]{1,2,3,4,5}));   // 4
        System.out.println(maxProfit(new int[]{7,6,4,3,1}));   // 0
    }
}
