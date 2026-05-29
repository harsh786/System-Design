/**
 * Problem: Problem39 MonotonicQueueLogSeverityWindow - Track max severity in rolling log window for alerting.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Track max severity in rolling log window for alerting.
 */
import java.util.*;

public class Problem39_MonotonicQueueLogSeverityWindow {
    private final Deque<int[]> maxSev = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem39_MonotonicQueueLogSeverityWindow(int windowSize) { this.windowSize = windowSize; }

    public int addLog(int severity) {
        while (!maxSev.isEmpty() && maxSev.peekFirst()[1] <= idx - windowSize) maxSev.pollFirst();
        while (!maxSev.isEmpty() && maxSev.peekLast()[0] <= severity) maxSev.pollLast();
        maxSev.offerLast(new int[]{severity, idx++});
        return maxSev.peekFirst()[0];
    }

    public boolean shouldAlert(int threshold) { return !maxSev.isEmpty() && maxSev.peekFirst()[0] >= threshold; }

    public static void main(String[] args) {
        Problem39_MonotonicQueueLogSeverityWindow logger = new Problem39_MonotonicQueueLogSeverityWindow(4);
        int[] severities = {1, 2, 5, 3, 1, 1, 4};
        for (int s : severities) System.out.println("Sev " + s + " -> max=" + logger.addLog(s) + " alert=" + logger.shouldAlert(4));
    }
}
