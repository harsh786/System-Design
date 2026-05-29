/**
 * Problem: Deque-Based Rate Limiter
 * Deque of timestamps, remove expired entries, check count <= limit.
 * Time: O(n) | Space: O(n)
 * Production Analogy: API rate limiting - allow N requests per time window.
 */
import java.util.*;

public class Problem21_DequeBasedRateLimiter {
    private final int limit;
    private final long windowMs;
    private final Deque<Long> timestamps = new ArrayDeque<>();

    public Problem21_DequeBasedRateLimiter(int limit, long windowMs) { this.limit = limit; this.windowMs = windowMs; }

    public synchronized boolean allowRequest() {
        long now = System.currentTimeMillis();
        while (!timestamps.isEmpty() && timestamps.peekFirst() <= now - windowMs) timestamps.pollFirst();
        if (timestamps.size() < limit) { timestamps.offerLast(now); return true; }
        return false;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem21_DequeBasedRateLimiter rl = new Problem21_DequeBasedRateLimiter(3, 1000);
        for (int i = 0; i < 5; i++) System.out.println("Request " + i + ": " + (rl.allowRequest() ? "ALLOWED" : "DENIED"));
        Thread.sleep(1100);
        System.out.println("After wait: " + (rl.allowRequest() ? "ALLOWED" : "DENIED"));
    }
}
