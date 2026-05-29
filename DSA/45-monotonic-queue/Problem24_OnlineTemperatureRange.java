/**
 * Problem: Online Temperature Range
 * Two deques tracking min/max temperature in rolling window.
 * Time: O(n) | Space: O(n)
 * Production Analogy: IoT sensor monitoring - alert when temperature range exceeds threshold.
 */
import java.util.*;

public class Problem24_OnlineTemperatureRange {
    private final int windowSize;
    private final Deque<int[]> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
    private int idx = 0;

    public Problem24_OnlineTemperatureRange(int windowSize) { this.windowSize = windowSize; }

    public int[] addReading(int temp) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= idx - windowSize) maxD.pollFirst();
        while (!minD.isEmpty() && minD.peekFirst()[1] <= idx - windowSize) minD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= temp) maxD.pollLast();
        while (!minD.isEmpty() && minD.peekLast()[0] >= temp) minD.pollLast();
        maxD.offerLast(new int[]{temp, idx}); minD.offerLast(new int[]{temp, idx}); idx++;
        return new int[]{minD.peekFirst()[0], maxD.peekFirst()[0]};
    }

    public static void main(String[] args) {
        Problem24_OnlineTemperatureRange tr = new Problem24_OnlineTemperatureRange(3);
        int[] temps = {72, 75, 68, 80, 65};
        for (int t : temps) { int[] r = tr.addReading(t); System.out.println("Temp " + t + " -> range [" + r[0] + ", " + r[1] + "]"); }
    }
}
