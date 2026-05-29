import java.util.*;

public class Problem30_BestTimeToBuyAndSellStockIV {
    private Integer[][][] memo;

    public int maxProfit(int k, int[] prices) {
        memo = new Integer[prices.length][k + 1][2];
        return helper(prices, 0, k, 0);
    }

    private int helper(int[] prices, int i, int k, int holding) {
        if (i >= prices.length || k == 0) return 0;
        if (memo[i][k][holding] != null) return memo[i][k][holding];
        int skip = helper(prices, i + 1, k, holding);
        int act;
        if (holding == 0) act = -prices[i] + helper(prices, i + 1, k, 1);
        else act = prices[i] + helper(prices, i + 1, k - 1, 0);
        memo[i][k][holding] = Math.max(skip, act);
        return memo[i][k][holding];
    }

    public static void main(String[] args) {
        Problem30_BestTimeToBuyAndSellStockIV sol = new Problem30_BestTimeToBuyAndSellStockIV();
        System.out.println(sol.maxProfit(2, new int[]{3,2,6,5,0,3})); // 7
    }
}
