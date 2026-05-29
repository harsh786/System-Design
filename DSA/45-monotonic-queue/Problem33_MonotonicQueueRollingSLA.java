/**
 * Problem: Problem33 MonotonicQueueRollingSLA - Monitor SLA compliance over rolling windows using monotonic deque.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Monitor SLA compliance over rolling windows using monotonic deque.
 */
import java.util.*;

public class Problem33_MonotonicQueueRollingSLA {
    // Monitor if p99 latency stays below SLA threshold in rolling window
    private final Deque<long[]> maxLatency = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem33_MonotonicQueueRollingSLA(int windowSize) { this.windowSize = windowSize; }

    public boolean checkSLA(long latency, long threshold) {
        while (!maxLatency.isEmpty() && maxLatency.peekFirst()[1] <= idx - windowSize) maxLatency.pollFirst();
        while (!maxLatency.isEmpty() && maxLatency.peekLast()[0] <= latency) maxLatency.pollLast();
        maxLatency.offerLast(new long[]{latency, idx++});
        return maxLatency.peekFirst()[0] <= threshold;
    }

    public static void main(String[] args) {
        Problem33_MonotonicQueueRollingSLA sla = new Problem33_MonotonicQueueRollingSLA(5);
        long[] latencies = {50, 80, 120, 60, 40, 30, 25};
        for (long l : latencies) System.out.println("Latency " + l + "ms -> SLA OK: " + sla.checkSLA(l, 100));
    }
}
