/**
 * Problem: Problem37 MonotonicQueueWindowedInventory - Track min inventory levels over time windows for reorder alerts.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Track min inventory levels over time windows for reorder alerts.
 */
import java.util.*;

public class Problem37_MonotonicQueueWindowedInventory {
    private final Deque<int[]> minD = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem37_MonotonicQueueWindowedInventory(int windowSize) { this.windowSize = windowSize; }

    public int addLevel(int level) {
        while (!minD.isEmpty() && minD.peekFirst()[1] <= idx - windowSize) minD.pollFirst();
        while (!minD.isEmpty() && minD.peekLast()[0] >= level) minD.pollLast();
        minD.offerLast(new int[]{level, idx++});
        return minD.peekFirst()[0];
    }

    public boolean shouldReorder(int threshold) { return !minD.isEmpty() && minD.peekFirst()[0] < threshold; }

    public static void main(String[] args) {
        Problem37_MonotonicQueueWindowedInventory inv = new Problem37_MonotonicQueueWindowedInventory(3);
        int[] levels = {50, 45, 30, 35, 20, 40};
        for (int l : levels) System.out.println("Stock " + l + " -> min=" + inv.addLevel(l) + " reorder=" + inv.shouldReorder(25));
    }
}
