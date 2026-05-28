/**
 * Problem 36: Best Time to Buy and Sell Stock with Transaction Fee
 * 
 * Unlimited transactions but each has a fee.
 * 
 * States: hold (have stock), cash (no stock)
 * Time: O(n), Space: O(1)
 */
public class Problem36_BestTimeToBuyAndSellStockWithTransactionFee {

    public static int maxProfit(int[] prices, int fee) {
        int cash = 0, hold = -prices[0];
        for (int i = 1; i < prices.length; i++) {
            cash = Math.max(cash, hold + prices[i] - fee);
            hold = Math.max(hold, cash - prices[i]);
        }
        return cash;
    }

    public static void main(String[] args) {
        System.out.println("=== Stock with Fee ===");
        System.out.println(maxProfit(new int[]{1,3,2,8,4,9}, 2)); // 8
        System.out.println(maxProfit(new int[]{1,3,7,5,10,3}, 3)); // 6
    }
}
