import java.util.*;

public class Problem02_CoinChange {
    private Map<Integer, Integer> memo = new HashMap<>();

    public int coinChange(int[] coins, int amount) {
        if (amount == 0) return 0;
        if (amount < 0) return -1;
        if (memo.containsKey(amount)) return memo.get(amount);
        int min = Integer.MAX_VALUE;
        for (int coin : coins) {
            int sub = coinChange(coins, amount - coin);
            if (sub >= 0) min = Math.min(min, sub + 1);
        }
        int result = (min == Integer.MAX_VALUE) ? -1 : min;
        memo.put(amount, result);
        return result;
    }

    public static void main(String[] args) {
        Problem02_CoinChange sol = new Problem02_CoinChange();
        System.out.println("Coin Change [1,5,10] amount=11: " + sol.coinChange(new int[]{1,5,10}, 11)); // 2
    }
}
