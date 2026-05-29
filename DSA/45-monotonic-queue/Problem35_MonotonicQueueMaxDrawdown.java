/**
 * Problem: Problem35 MonotonicQueueMaxDrawdown - Calculate maximum drawdown (peak-to-trough) in rolling window.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Calculate maximum drawdown (peak-to-trough) in rolling window.
 */
import java.util.*;

public class Problem35_MonotonicQueueMaxDrawdown {
    // Max drawdown = max(peak - trough) where peak comes before trough in window
    public static double maxDrawdown(double[] prices, int window) {
        Deque<Integer> maxD = new ArrayDeque<>(); // tracks max (peak)
        double maxDD = 0;
        for (int i = 0; i < prices.length; i++) {
            while (!maxD.isEmpty() && maxD.peekFirst() < i - window + 1) maxD.pollFirst();
            while (!maxD.isEmpty() && prices[maxD.peekLast()] <= prices[i]) maxD.pollLast();
            maxD.offerLast(i);
            // Drawdown from peak to current
            double dd = prices[maxD.peekFirst()] - prices[i];
            if (dd > 0) maxDD = Math.max(maxDD, dd);
        }
        return maxDD;
    }

    public static void main(String[] args) {
        double[] prices = {100, 110, 105, 95, 102, 88, 92};
        System.out.println("Max drawdown (window 4): " + maxDrawdown(prices, 4));
        System.out.println("Max drawdown (full): " + maxDrawdown(prices, prices.length));
    }
}
