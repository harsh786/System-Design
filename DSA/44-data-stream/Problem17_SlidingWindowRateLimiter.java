import java.util.*;

public class Problem17_SlidingWindowRateLimiter {
    // Sliding Window Rate Limiter: Allow max N requests per window of W seconds.
    
    int maxRequests;
    int windowMs;
    Deque<Long> timestamps = new ArrayDeque<>();
    
    public Problem17_SlidingWindowRateLimiter() { this.maxRequests = 5; this.windowMs = 1000; }
    
    public void init(int maxRequests, int windowMs) {
        this.maxRequests = maxRequests;
        this.windowMs = windowMs;
    }
    
    public boolean allowRequest(long timestamp) {
        while (!timestamps.isEmpty() && timestamps.peekFirst() <= timestamp - windowMs)
            timestamps.pollFirst();
        if (timestamps.size() < maxRequests) { timestamps.offerLast(timestamp); return true; }
        return false;
    }
    
    public static void main(String[] args) {
        Problem17_SlidingWindowRateLimiter sol = new Problem17_SlidingWindowRateLimiter();
        sol.init(3, 1000);
        System.out.println(sol.allowRequest(100));  // true
        System.out.println(sol.allowRequest(200));  // true
        System.out.println(sol.allowRequest(300));  // true
        System.out.println(sol.allowRequest(400));  // false
        System.out.println(sol.allowRequest(1100)); // true (first expired)
    }
}
