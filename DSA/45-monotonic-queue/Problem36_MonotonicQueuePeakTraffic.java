/**
 * Problem: Problem36 MonotonicQueuePeakTraffic - Identify peak traffic periods using monotonic deque on request counts.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Identify peak traffic periods using monotonic deque on request counts.
 */
import java.util.*;

public class Problem36_MonotonicQueuePeakTraffic {
    private final Deque<int[]> maxD = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem36_MonotonicQueuePeakTraffic(int windowSize) { this.windowSize = windowSize; }

    public int addRequestCount(int count) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= idx - windowSize) maxD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= count) maxD.pollLast();
        maxD.offerLast(new int[]{count, idx++});
        return maxD.peekFirst()[0];
    }

    public static void main(String[] args) {
        Problem36_MonotonicQueuePeakTraffic pt = new Problem36_MonotonicQueuePeakTraffic(3);
        int[] traffic = {100, 250, 180, 300, 150, 120};
        for (int t : traffic) System.out.println("Requests " + t + " -> peak in window: " + pt.addRequestCount(t));
    }
}
