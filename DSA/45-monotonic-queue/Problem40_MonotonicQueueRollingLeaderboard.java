/**
 * Problem: Problem40 MonotonicQueueRollingLeaderboard - Maintain rolling top score using monotonic deque.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Maintain rolling top score using monotonic deque.
 */
import java.util.*;

public class Problem40_MonotonicQueueRollingLeaderboard {
    private final Deque<int[]> maxD = new ArrayDeque<>();
    private final int windowSize;
    private int idx = 0;

    public Problem40_MonotonicQueueRollingLeaderboard(int windowSize) { this.windowSize = windowSize; }

    public int addScore(int score) {
        while (!maxD.isEmpty() && maxD.peekFirst()[1] <= idx - windowSize) maxD.pollFirst();
        while (!maxD.isEmpty() && maxD.peekLast()[0] <= score) maxD.pollLast();
        maxD.offerLast(new int[]{score, idx++});
        return maxD.peekFirst()[0];
    }

    public static void main(String[] args) {
        Problem40_MonotonicQueueRollingLeaderboard lb = new Problem40_MonotonicQueueRollingLeaderboard(3);
        int[] scores = {85, 92, 78, 95, 88, 70};
        for (int s : scores) System.out.println("Score " + s + " -> top in window: " + lb.addScore(s));
    }
}
