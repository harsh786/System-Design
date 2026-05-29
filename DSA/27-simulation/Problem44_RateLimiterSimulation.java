/**
 * Problem: Rate Limiter Simulation (Token Bucket + Sliding Window)
 * Approach: Token bucket algorithm with refill rate
 * Complexity: O(1) per request
 * Production Analogy: API gateway rate limiting (nginx, Envoy, API Gateway)
 */
public class Problem44_RateLimiterSimulation {
    private final int maxTokens;
    private final double refillRate; // tokens per ms
    private double tokens;
    private long lastRefill;

    public Problem44_RateLimiterSimulation(int maxTokens, int refillPerSecond) {
        this.maxTokens = maxTokens;
        this.refillRate = refillPerSecond / 1000.0;
        this.tokens = maxTokens;
        this.lastRefill = System.currentTimeMillis();
    }

    public synchronized boolean allowRequest() {
        long now = System.currentTimeMillis();
        tokens = Math.min(maxTokens, tokens + (now - lastRefill) * refillRate);
        lastRefill = now;
        if (tokens >= 1) { tokens--; return true; }
        return false;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem44_RateLimiterSimulation limiter = new Problem44_RateLimiterSimulation(5, 2);
        for (int i = 0; i < 10; i++) {
            System.out.println("Request " + i + ": " + limiter.allowRequest());
            Thread.sleep(200);
        }
    }
}
