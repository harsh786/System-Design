import java.util.Arrays;

/**
 * Problem 48: Sell Diminishing-Valued Colored Balls
 * 
 * Ball of color i with inventory[i] count sells for current count value, then decreases.
 * Sell exactly 'orders' balls to maximize profit.
 * 
 * Approach: Binary search for threshold value T. Sell all balls with value > T.
 * Then sell remaining at exactly T.
 * 
 * Time: O(n log(max)), Space: O(1)
 * 
 * Production Analogy: Pricing compute instances with diminishing returns —
 * finding optimal price floor to fill exactly k orders maximizing revenue.
 */
public class Problem48_SellDiminishingValuedColoredBalls {
    private static final int MOD = 1_000_000_007;

    public static int maxProfit(int[] inventory, int orders) {
        int lo = 0, hi = 0;
        for (int inv : inventory) hi = Math.max(hi, inv);
        
        // Find threshold: largest T such that total balls with value > T >= orders
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (countAbove(inventory, mid) <= orders) hi = mid;
            else lo = mid + 1;
        }
        // lo is the threshold
        int threshold = lo;
        long profit = 0;
        long remaining = orders;
        
        for (int inv : inventory) {
            if (inv > threshold) {
                // Sell from inv down to threshold+1: sum = (threshold+1 + inv) * count / 2
                long count = inv - threshold;
                profit = (profit + sumRange(threshold + 1, inv)) % MOD;
                remaining -= count;
            }
        }
        // Sell remaining at threshold
        profit = (profit + (long) threshold % MOD * (remaining % MOD)) % MOD;
        return (int) profit;
    }

    private static long countAbove(int[] inventory, int threshold) {
        long count = 0;
        for (int inv : inventory) if (inv > threshold) count += inv - threshold;
        return count;
    }

    private static long sumRange(long lo, long hi) {
        return (lo + hi) * (hi - lo + 1) / 2 % MOD;
    }

    public static void main(String[] args) {
        System.out.println(maxProfit(new int[]{2,5}, 4));          // 14
        System.out.println(maxProfit(new int[]{3,5}, 6));          // 19
        System.out.println(maxProfit(new int[]{2,8,4,10,6}, 20)); // 110
    }
}
