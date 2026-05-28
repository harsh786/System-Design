/**
 * Problem 19: Best Time to Buy and Sell Stock with Cooldown
 * 
 * After selling, must wait one day before buying again.
 * 
 * States: hold, sold, rest
 * hold[i] = max(hold[i-1], rest[i-1] - prices[i])
 * sold[i] = hold[i-1] + prices[i]
 * rest[i] = max(rest[i-1], sold[i-1])
 * 
 * Time: O(n), Space: O(1)
 */
public class Problem19_BestTimeToBuyAndSellStockWithCooldown {

    public static int maxProfit(int[] prices) {
        if (prices.length < 2) return 0;
        int hold = -prices[0], sold = 0, rest = 0;
        for (int i = 1; i < prices.length; i++) {
            int newHold = Math.max(hold, rest - prices[i]);
            int newSold = hold + prices[i];
            int newRest = Math.max(rest, sold);
            hold = newHold; sold = newSold; rest = newRest;
        }
        return Math.max(sold, rest);
    }

    public static void main(String[] args) {
        System.out.println("=== Stock with Cooldown ===");
        System.out.println(maxProfit(new int[]{1,2,3,0,2})); // 3
        System.out.println(maxProfit(new int[]{1})); // 0
    }
}
