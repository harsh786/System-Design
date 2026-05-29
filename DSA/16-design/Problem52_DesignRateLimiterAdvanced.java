import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 52: Rate Limiter - Token Bucket + Sliding Window Log + Fixed Window Counter
 * 
 * PRODUCTION MAPPING: API Gateways (Kong, Envoy), Cloudflare, AWS API Gateway, Stripe
 * 
 * Three algorithms implemented:
 * 1. Token Bucket: Smooth rate limiting, allows bursts up to bucket size
 *    - Used by: AWS API Gateway, Stripe
 *    - Pros: Handles bursts, memory efficient
 *    - Cons: Burst at boundary possible
 * 
 * 2. Sliding Window Log: Exact counting, no boundary issues
 *    - Used by: Rate limiters needing precision
 *    - Pros: Most accurate
 *    - Cons: O(n) memory per user (stores all timestamps)
 * 
 * 3. Fixed Window Counter: Simplest, but boundary problem
 *    - Used by: Simple API rate limits
 *    - Pros: O(1) memory, fast
 *    - Cons: 2x burst at window boundary
 * 
 * Staff-level insight: In production, you often combine these.
 * Example: Token bucket for burst control + sliding window for sustained rate.
 */
public class Problem52_DesignRateLimiterAdvanced {

    // ============ 1. TOKEN BUCKET ============
    static class TokenBucket {
        private final int maxTokens;       // bucket capacity
        private final double refillRate;   // tokens per second
        private double currentTokens;
        private long lastRefillTime;

        public TokenBucket(int maxTokens, double refillRate) {
            this.maxTokens = maxTokens;
            this.refillRate = refillRate;
            this.currentTokens = maxTokens;
            this.lastRefillTime = System.nanoTime();
        }

        public synchronized boolean allowRequest(int tokens) {
            refill();
            if (currentTokens >= tokens) {
                currentTokens -= tokens;
                return true;
            }
            return false;
        }

        private void refill() {
            long now = System.nanoTime();
            double elapsed = (now - lastRefillTime) / 1_000_000_000.0;
            currentTokens = Math.min(maxTokens, currentTokens + elapsed * refillRate);
            lastRefillTime = now;
        }

        public synchronized double getTokens() { return currentTokens; }
    }

    // ============ 2. SLIDING WINDOW LOG ============
    static class SlidingWindowLog {
        private final int maxRequests;
        private final long windowSizeMs;
        private final Deque<Long> timestamps; // sorted request timestamps

        public SlidingWindowLog(int maxRequests, long windowSizeMs) {
            this.maxRequests = maxRequests;
            this.windowSizeMs = windowSizeMs;
            this.timestamps = new ArrayDeque<>();
        }

        public synchronized boolean allowRequest() {
            long now = System.currentTimeMillis();
            // Remove expired timestamps
            while (!timestamps.isEmpty() && now - timestamps.peekFirst() > windowSizeMs) {
                timestamps.pollFirst();
            }
            if (timestamps.size() < maxRequests) {
                timestamps.addLast(now);
                return true;
            }
            return false;
        }

        public synchronized int getCurrentCount() { return timestamps.size(); }
    }

    // ============ 3. FIXED WINDOW COUNTER ============
    static class FixedWindowCounter {
        private final int maxRequests;
        private final long windowSizeMs;
        private long windowStart;
        private int counter;

        public FixedWindowCounter(int maxRequests, long windowSizeMs) {
            this.maxRequests = maxRequests;
            this.windowSizeMs = windowSizeMs;
            this.windowStart = System.currentTimeMillis();
            this.counter = 0;
        }

        public synchronized boolean allowRequest() {
            long now = System.currentTimeMillis();
            if (now - windowStart >= windowSizeMs) {
                windowStart = now;
                counter = 0;
            }
            if (counter < maxRequests) {
                counter++;
                return true;
            }
            return false;
        }

        public synchronized int getCurrentCount() { return counter; }
    }

    // ============ COMPOSITE: Multi-tier rate limiter ============
    static class CompositeRateLimiter {
        private final TokenBucket burstLimiter;
        private final SlidingWindowLog sustainedLimiter;

        /**
         * Production pattern: combine burst + sustained limits
         * Example: Allow 10 requests burst, but max 100/minute sustained
         */
        public CompositeRateLimiter(int burstSize, double refillRate, 
                                     int sustainedMax, long sustainedWindowMs) {
            this.burstLimiter = new TokenBucket(burstSize, refillRate);
            this.sustainedLimiter = new SlidingWindowLog(sustainedMax, sustainedWindowMs);
        }

        public boolean allowRequest() {
            // Must pass BOTH checks
            return burstLimiter.allowRequest(1) && sustainedLimiter.allowRequest();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Advanced Rate Limiter Implementations ===\n");

        // Test Token Bucket
        System.out.println("--- Token Bucket ---");
        TokenBucket tb = new TokenBucket(5, 2.0); // 5 max, 2/sec refill
        int allowed = 0;
        for (int i = 0; i < 10; i++) {
            if (tb.allowRequest(1)) allowed++;
        }
        assert allowed == 5 : "Should allow exactly 5 burst requests";
        System.out.println("PASS: Burst limited to bucket size (5 of 10 allowed)");
        
        Thread.sleep(1000); // wait for refill
        allowed = 0;
        for (int i = 0; i < 3; i++) {
            if (tb.allowRequest(1)) allowed++;
        }
        assert allowed >= 2 : "Should allow ~2 after 1s refill";
        System.out.println("PASS: Tokens refilled after wait (" + allowed + " allowed)");

        // Test Sliding Window Log
        System.out.println("\n--- Sliding Window Log ---");
        SlidingWindowLog swl = new SlidingWindowLog(5, 1000); // 5 per second
        allowed = 0;
        for (int i = 0; i < 10; i++) {
            if (swl.allowRequest()) allowed++;
        }
        assert allowed == 5 : "Should allow exactly 5";
        System.out.println("PASS: Sliding window limits to 5 requests");
        
        Thread.sleep(1100); // wait for window to pass
        assert swl.allowRequest() : "Should allow after window expires";
        System.out.println("PASS: Window expires correctly");

        // Test Fixed Window Counter
        System.out.println("\n--- Fixed Window Counter ---");
        FixedWindowCounter fwc = new FixedWindowCounter(3, 1000);
        allowed = 0;
        for (int i = 0; i < 5; i++) {
            if (fwc.allowRequest()) allowed++;
        }
        assert allowed == 3 : "Should allow exactly 3";
        System.out.println("PASS: Fixed window limits correctly");

        Thread.sleep(1100);
        assert fwc.allowRequest() : "New window should allow";
        System.out.println("PASS: Counter resets in new window");

        // Test Composite
        System.out.println("\n--- Composite Rate Limiter ---");
        CompositeRateLimiter crl = new CompositeRateLimiter(3, 1.0, 10, 5000);
        allowed = 0;
        for (int i = 0; i < 5; i++) {
            if (crl.allowRequest()) allowed++;
        }
        assert allowed == 3 : "Burst limit should cap at 3";
        System.out.println("PASS: Composite limiter respects burst limit");

        // Test multi-cost requests (Token Bucket)
        System.out.println("\n--- Multi-cost Token Bucket ---");
        TokenBucket tb2 = new TokenBucket(10, 5.0);
        assert tb2.allowRequest(5) : "Should allow 5-token request";
        assert tb2.allowRequest(5) : "Should allow second 5-token request";
        assert !tb2.allowRequest(1) : "Should deny, bucket empty";
        System.out.println("PASS: Multi-cost requests work correctly");

        System.out.println("\nAll tests passed!");
    }
}
