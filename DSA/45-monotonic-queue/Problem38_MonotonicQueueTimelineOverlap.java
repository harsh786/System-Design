/**
 * Problem: Problem38 MonotonicQueueTimelineOverlap - Find max overlap in timeline events using sweep line + deque.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Find max overlap in timeline events using sweep line + deque.
 */
import java.util.*;

public class Problem38_MonotonicQueueTimelineOverlap {
    // Max concurrent events using sweep line
    public static int maxOverlap(int[][] intervals) {
        List<int[]> events = new ArrayList<>();
        for (int[] iv : intervals) { events.add(new int[]{iv[0], 1}); events.add(new int[]{iv[1], -1}); }
        events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        int max = 0, current = 0;
        for (int[] e : events) { current += e[1]; max = Math.max(max, current); }
        return max;
    }

    public static void main(String[] args) {
        int[][] intervals = {{1,4},{2,5},{3,6},{5,8}};
        System.out.println("Max overlap: " + maxOverlap(intervals)); // 3
    }
}
