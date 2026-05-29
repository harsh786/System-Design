import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 50: Design Rate Limiter (Token Bucket + Sliding Window)
 * 
 * API Contract:
 * - TokenBucket.allow(): Return true if request is allowed (consume 1 token)
 * - SlidingWindowLog.allow(userId): Return true if user hasn't exceeded limit
 * - SlidingWindowCounter.allow(): Approximate sliding window using fixed windows
 * 
 * Complexity: Token Bucket O(1), Sliding Window Log O(n), Counter O(1)
 * 
 * Production Analogy: API gateway rate limiting (Kong, Envoy), DDoS protection,
 * AWS API Gateway throttling, Redis-based distributed rate limiters,
 * Stripe/GitHub API rate limits, Nginx limit_req module
 */
public class Problem50_DesignRateLimiter {

    /**
     * Token Bucket Algorithm:
     * - Tokens added at fixed rate
     * - Burst allowed up to bucket capacity
     * - Each request consumes one token
     * Used by: AWS, Stripe, most API gateways
     */
    static class TokenBucket {
        private double tokens;
        private double maxTokens;
        private double refillRate; // tokens per second
        private long lastRefillTime;

        public TokenBucket(double maxTokens, double refillRate) {
            this.maxTokens = maxTokens;
            this.refillRate = refillRate;
            this.tokens = maxTokens;
            this.lastRefillTime = System.nanoTime();
        }

        public synchronized boolean allow() {
            refill();
            if (tokens >= 1) { tokens--; return true; }
            return false;
        }

        private void refill() {
            long now = System.nanoTime();
            double elapsed = (now - lastRefillTime) / 1e9;
            tokens = Math.min(maxTokens, tokens + elapsed * refillRate);
            lastRefillTime = now;
        }
    }

    /**
     * Sliding Window Log Algorithm:
     * - Keep timestamp of each request
     * - Count requests in [now - window, now]
     * - Exact but memory-intensive
     * Used by: Strict per-user rate limiting
     */
    static class SlidingWindowLog {
        private Map<String, Deque<Long>> userLogs;
        private int maxRequests;
        private long windowMs;

        public SlidingWindowLog(int maxRequests, long windowMs) {
            this.maxRequests = maxRequests;
            this.windowMs = windowMs;
            userLogs = new ConcurrentHashMap<>();
        }

        public boolean allow(String userId) {
            long now = System.currentTimeMillis();
            Deque<Long> log = userLogs.computeIfAbsent(userId, k -> new ArrayDeque<>());
            synchronized (log) {
                // Remove expired entries
                while (!log.isEmpty() && now - log.peekFirst() >= windowMs)
                    log.pollFirst();
                if (log.size() < maxRequests) { log.offerLast(now); return true; }
                return false;
            }
        }
    }

    /**
     * Sliding Window Counter (Approximate):
     * - Combines current and previous fixed window counts
     * - Weight = overlap percentage with previous window
     * - Memory efficient: O(1) per user
     * Used by: High-throughput systems where approximation is acceptable
     */
    static class SlidingWindowCounter {
        private int maxRequests;
        private long windowMs;
        private Map<String, long[]> windows; // [prevCount, currCount, windowStart]

        public SlidingWindowCounter(int maxRequests, long windowMs) {
            this.maxRequests = maxRequests;
            this.windowMs = windowMs;
            windows = new ConcurrentHashMap<>();
        }

        public boolean allow(String userId) {
            long now = System.currentTimeMillis();
            long[] state = windows.computeIfAbsent(userId, k -> new long[]{0, 0, now});
            synchronized (state) {
                long windowStart = state[2];
                if (now - windowStart >= 2 * windowMs) {
                    state[0] = 0; state[1] = 0; state[2] = now;
                } else if (now - windowStart >= windowMs) {
                    state[0] = state[1]; state[1] = 0; state[2] = windowStart + windowMs;
                }
                // Calculate weighted count
                double elapsed = (now - state[2]) / (double) windowMs;
                double weight = 1.0 - elapsed;
                double count = state[0] * weight + state[1];
                if (count < maxRequests) { state[1]++; return true; }
                return false;
            }
        }
    }

    public static void main(String[] args) throws Exception {
        // Token Bucket test
        TokenBucket tb = new TokenBucket(5, 1); // 5 max, 1/sec refill
        int allowed = 0;
        for (int i = 0; i < 10; i++) if (tb.allow()) allowed++;
        assert allowed == 5 : "Token bucket should allow 5 burst, got " + allowed;

        // Sliding Window Log test
        SlidingWindowLog swl = new SlidingWindowLog(3, 1000); // 3 req per sec
        assert swl.allow("user1");
        assert swl.allow("user1");
        assert swl.allow("user1");
        assert !swl.allow("user1"); // 4th blocked
        assert swl.allow("user2"); // different user OK

        // After window expires
        Thread.sleep(1100);
        assert swl.allow("user1"); // window reset

        // Sliding Window Counter test
        SlidingWindowCounter swc = new SlidingWindowCounter(5, 1000);
        for (int i = 0; i < 5; i++) assert swc.allow("u1");
        assert !swc.allow("u1"); // 6th blocked

        System.out.println("All tests passed!");
    }
}
