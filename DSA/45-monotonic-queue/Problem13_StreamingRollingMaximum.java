/**
 * Problem: Streaming Rolling Maximum
 * Online monotonic deque processing streaming data points.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Real-time dashboard showing peak load over rolling window.
 */
import java.util.*;

public class Problem13_StreamingRollingMaximum {
    private final int windowSize;
    private final Deque<int[]> deque = new ArrayDeque<>(); // [value, index]
    private int index = 0;

    public Problem13_StreamingRollingMaximum(int windowSize) { this.windowSize = windowSize; }

    public int add(int val) {
        while (!deque.isEmpty() && deque.peekFirst()[1] <= index - windowSize) deque.pollFirst();
        while (!deque.isEmpty() && deque.peekLast()[0] <= val) deque.pollLast();
        deque.offerLast(new int[]{val, index++});
        return deque.peekFirst()[0];
    }

    public static void main(String[] args) {
        Problem13_StreamingRollingMaximum rm = new Problem13_StreamingRollingMaximum(3);
        int[] stream = {1, 3, 2, 5, 1, 4};
        for (int v : stream) System.out.println("Add " + v + " -> max = " + rm.add(v));
    }
}
