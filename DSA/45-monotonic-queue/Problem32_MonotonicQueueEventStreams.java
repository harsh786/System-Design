/**
 * Problem: Problem32 MonotonicQueueEventStreams - Process event streams maintaining max/min over sliding time windows.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Process event streams maintaining max/min over sliding time windows.
 */
import java.util.*;

public class Problem32_MonotonicQueueEventStreams {
    private final int windowSize;
    private final Deque<long[]> maxD = new ArrayDeque<>(); // [value, seq]
    private long seq = 0;

    public Problem32_MonotonicQueueEventStreams(int windowSize) { this.windowSize = windowSize; }

    public long processEvent(long value) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= seq - windowSize) maxD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= value) maxD.pollLast();
        maxD.offerLast(new long[]{value, seq++});
        return maxD.peekFirst()[0];
    }

    public static void main(String[] args) {
        Problem32_MonotonicQueueEventStreams es = new Problem32_MonotonicQueueEventStreams(3);
        long[] events = {10, 5, 15, 8, 12, 3};
        for (long e : events) System.out.println("Event " + e + " -> window max = " + es.processEvent(e));
    }
}
