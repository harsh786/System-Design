/**
 * Problem 1: Best Time to Buy and Sell Stock (LeetCode 121)
 * 
 * Approach: Sliding window / one-pass tracking minimum price seen so far.
 * Window invariant: track the minimum price in the window [0..i] and max profit.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like monitoring the lowest latency baseline and tracking
 * the maximum deviation (spike) from that baseline in a streaming metrics system.
 */
public class Problem01_BestTimeToBuyAndSellStock {
    public static int maxProfit(int[] prices) {
        if (prices == null || prices.length < 2) return 0;
        int minPrice = prices[0];
        int maxProfit = 0;
        for (int i = 1; i < prices.length; i++) {
            maxProfit = Math.max(maxProfit, prices[i] - minPrice);
            minPrice = Math.min(minPrice, prices[i]);
        }
        return maxProfit;
    }

    public static void main(String[] args) {
        System.out.println(maxProfit(new int[]{7,1,5,3,6,4})); // 5
        System.out.println(maxProfit(new int[]{7,6,4,3,1}));   // 0
        System.out.println(maxProfit(new int[]{1,2}));          // 1
        System.out.println(maxProfit(new int[]{2,1,2,1,0,1,2})); // 2
        System.out.println(maxProfit(new int[]{}));             // 0
        System.out.println(maxProfit(new int[]{1}));            // 0
    }
}
