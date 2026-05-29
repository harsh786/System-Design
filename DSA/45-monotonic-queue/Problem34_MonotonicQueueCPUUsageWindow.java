/**
 * Problem: Problem34 MonotonicQueueCPUUsageWindow - Track peak CPU usage in time windows for autoscaling decisions.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Track peak CPU usage in time windows for autoscaling decisions.
 */
import java.util.*;

public class Problem34_MonotonicQueueCPUUsageWindow {
    private final Deque<int[]> maxD = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem34_MonotonicQueueCPUUsageWindow(int windowSize) { this.windowSize = windowSize; }

    public int addSample(int cpuPercent) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= idx - windowSize) maxD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= cpuPercent) maxD.pollLast();
        maxD.offerLast(new int[]{cpuPercent, idx++});
        return maxD.peekFirst()[0];
    }

    public boolean shouldScaleUp(int threshold) { return !maxD.isEmpty() && maxD.peekFirst()[0] > threshold; }

    public static void main(String[] args) {
        Problem34_MonotonicQueueCPUUsageWindow cpu = new Problem34_MonotonicQueueCPUUsageWindow(4);
        int[] samples = {30, 45, 80, 60, 50, 90, 40};
        for (int s : samples) System.out.println("CPU " + s + "% -> peak=" + cpu.addSample(s) + " scale=" + cpu.shouldScaleUp(75));
    }
}
