/**
 * Problem: Problem26 MonotonicQueueStockPrices - Track max/min stock price in rolling window for trading signals.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Track max/min stock price in rolling window for trading signals.
 */
import java.util.*;

public class Problem26_MonotonicQueueStockPrices {
    private final int window;
    private final Deque<int[]> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
    private int idx = 0;

    public Problem26_MonotonicQueueStockPrices(int window) { this.window = window; }

    public int[] addPrice(int price) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= idx - window) maxD.pollFirst();
        while (!minD.isEmpty() && minD.peekFirst()[1] <= idx - window) minD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= price) maxD.pollLast();
        while (!minD.isEmpty() && minD.peekLast()[0] >= price) minD.pollLast();
        maxD.offerLast(new int[]{price, idx}); minD.offerLast(new int[]{price, idx}); idx++;
        return new int[]{minD.peekFirst()[0], maxD.peekFirst()[0]};
    }

    public static void main(String[] args) {
        Problem26_MonotonicQueueStockPrices sp = new Problem26_MonotonicQueueStockPrices(3);
        int[] prices = {100, 105, 98, 110, 95};
        for (int p : prices) { int[] r = sp.addPrice(p); System.out.println("Price " + p + " -> [" + r[0] + "," + r[1] + "]"); }
    }
}
