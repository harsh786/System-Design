/**
 * Problem 34: Best Time to Buy and Sell Stock III
 * 
 * At most 2 transactions.
 * 
 * Track 4 states: buy1, sell1, buy2, sell2
 * Time: O(n), Space: O(1)
 */
public class Problem34_BestTimeToBuyAndSellStockIII {

    public static int maxProfit(int[] prices) {
        int buy1 = Integer.MIN_VALUE, sell1 = 0;
        int buy2 = Integer.MIN_VALUE, sell2 = 0;
        for (int p : prices) {
            buy1 = Math.max(buy1, -p);
            sell1 = Math.max(sell1, buy1 + p);
            buy2 = Math.max(buy2, sell1 - p);
            sell2 = Math.max(sell2, buy2 + p);
        }
        return sell2;
    }

    public static void main(String[] args) {
        System.out.println("=== Stock III ===");
        System.out.println(maxProfit(new int[]{3,3,5,0,0,3,1,4})); // 6
        System.out.println(maxProfit(new int[]{1,2,3,4,5})); // 4
        System.out.println(maxProfit(new int[]{7,6,4,3,1})); // 0
    }
}
