/**
 * Problem: Rate Limiter with Concurrent Requests
 * Token bucket rate limiter safe for concurrent access.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: API gateway rate limiting (e.g., AWS API Gateway throttling).
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem12_RateLimiterConcurrent {
    private final int maxTokens;
    private double tokens;
    private long lastRefill;
    private final double refillRate; // tokens per ms

    public Problem12_RateLimiterConcurrent(int maxTokens, double refillPerSec) {
        this.maxTokens = maxTokens;
        this.tokens = maxTokens;
        this.refillRate = refillPerSec / 1000.0;
        this.lastRefill = System.currentTimeMillis();
    }

    public synchronized boolean tryAcquire() {
        refill();
        if (tokens >= 1) { tokens--; return true; }
        return false;
    }

    private void refill() {
        long now = System.currentTimeMillis();
        tokens = Math.min(maxTokens, tokens + (now - lastRefill) * refillRate);
        lastRefill = now;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem12_RateLimiterConcurrent rl = new Problem12_RateLimiterConcurrent(5, 2);
        for (int i = 0; i < 10; i++) {
            System.out.println("Request " + i + ": " + (rl.tryAcquire() ? "ALLOWED" : "DENIED"));
        }
        Thread.sleep(1500);
        System.out.println("After wait: " + (rl.tryAcquire() ? "ALLOWED" : "DENIED"));
    }
}
