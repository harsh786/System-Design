import java.util.*;

public class Problem29_BestTimeToBuyAndSellStockWithCooldown {
    private Integer[][] memo;

    public int maxProfit(int[] prices) {
        memo = new Integer[prices.length][2];
        return helper(prices, 0, 0);
    }

    // state: 0=can buy, 1=can sell
    private int helper(int[] prices, int i, int holding) {
        if (i >= prices.length) return 0;
        if (memo[i][holding] != null) return memo[i][holding];
        int skip = helper(prices, i + 1, holding);
        int act;
        if (holding == 0) act = -prices[i] + helper(prices, i + 1, 1);
        else act = prices[i] + helper(prices, i + 2, 0);
        memo[i][holding] = Math.max(skip, act);
        return memo[i][holding];
    }

    public static void main(String[] args) {
        Problem29_BestTimeToBuyAndSellStockWithCooldown sol = new Problem29_BestTimeToBuyAndSellStockWithCooldown();
        System.out.println(sol.maxProfit(new int[]{1,2,3,0,2})); // 3
    }
}
