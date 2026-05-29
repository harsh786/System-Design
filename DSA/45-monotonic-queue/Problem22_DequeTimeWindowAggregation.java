/**
 * Problem: Deque-Based Time Window Aggregation
 * Deque maintaining events within time window for sum/count/avg.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Real-time analytics - compute metrics over sliding time window.
 */
import java.util.*;

public class Problem22_DequeTimeWindowAggregation {
    private final long windowMs;
    private final Deque<long[]> events = new ArrayDeque<>(); // [timestamp, value]
    private long sum = 0;

    public Problem22_DequeTimeWindowAggregation(long windowMs) { this.windowMs = windowMs; }

    public void add(long timestamp, long value) {
        events.offerLast(new long[]{timestamp, value});
        sum += value;
        evict(timestamp);
    }

    private void evict(long now) {
        while (!events.isEmpty() && events.peekFirst()[0] <= now - windowMs) { sum -= events.pollFirst()[1]; }
    }

    public long getSum(long now) { evict(now); return sum; }
    public double getAvg(long now) { evict(now); return events.isEmpty() ? 0 : (double) sum / events.size(); }
    public int getCount(long now) { evict(now); return events.size(); }

    public static void main(String[] args) {
        Problem22_DequeTimeWindowAggregation agg = new Problem22_DequeTimeWindowAggregation(1000);
        agg.add(100, 5); agg.add(200, 10); agg.add(500, 3);
        System.out.println("Sum at 600: " + agg.getSum(600)); // 18
        System.out.println("Sum at 1200: " + agg.getSum(1200)); // 3
    }
}
