/**
 * Problem: Moving Average with Min-Max
 * Deque for min/max + running sum for average over window.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Financial technical analysis - Bollinger bands computation.
 */
import java.util.*;

public class Problem23_MovingAverageMinMax {
    private final int windowSize;
    private final Deque<Integer> data = new ArrayDeque<>();
    private final Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
    private long sum = 0;

    public Problem23_MovingAverageMinMax(int windowSize) { this.windowSize = windowSize; }

    public double[] add(int val) {
        data.offerLast(val); sum += val;
        while (!maxD.isEmpty() && maxD.peekLast() < val) maxD.pollLast(); maxD.offerLast(val);
        while (!minD.isEmpty() && minD.peekLast() > val) minD.pollLast(); minD.offerLast(val);
        if (data.size() > windowSize) {
            int removed = data.pollFirst(); sum -= removed;
            if (maxD.peekFirst() == removed) maxD.pollFirst();
            if (minD.peekFirst() == removed) minD.pollFirst();
        }
        return new double[]{(double) sum / data.size(), minD.peekFirst(), maxD.peekFirst()};
    }

    public static void main(String[] args) {
        Problem23_MovingAverageMinMax ma = new Problem23_MovingAverageMinMax(3);
        int[] vals = {1, 5, 3, 8, 2};
        for (int v : vals) { double[] r = ma.add(v); System.out.printf("Add %d -> avg=%.1f min=%.0f max=%.0f%n", v, r[0], r[1], r[2]); }
    }
}
