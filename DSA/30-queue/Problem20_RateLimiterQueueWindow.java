import java.util.*;

public class Problem20_RateLimiterQueueWindow {
    static class RateLimiter {
        private final Queue<Long> timestamps = new LinkedList<>();
        private final int maxRequests;
        private final long windowMs;
        RateLimiter(int maxRequests, long windowMs) { this.maxRequests = maxRequests; this.windowMs = windowMs; }
        synchronized boolean allowRequest(long timestamp) {
            while (!timestamps.isEmpty() && timestamps.peek() <= timestamp - windowMs) timestamps.poll();
            if (timestamps.size() < maxRequests) { timestamps.offer(timestamp); return true; }
            return false;
        }
    }
    public static void main(String[] args) {
        RateLimiter rl = new RateLimiter(3, 1000);
        System.out.println(rl.allowRequest(100));  // true
        System.out.println(rl.allowRequest(200));  // true
        System.out.println(rl.allowRequest(300));  // true
        System.out.println(rl.allowRequest(400));  // false
        System.out.println(rl.allowRequest(1100)); // true
    }
}
