import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem30_ConcurrentTokenBucketRateLimiter {
    /**
     * Problem: Concurrent Token Bucket Rate Limiter
     * Thread-safe token bucket using AtomicLong and CAS.
     * Approach: Lock-free with compareAndSet for token consumption.
     * Time: O(1)
     * Production Analogy: Nginx rate limiting, Envoy proxy circuit breaker.
     */
    private final AtomicLong tokens;
    private final long maxTokens;
    private final long refillRate;
    private final AtomicLong lastRefillTime;

    public Problem30_ConcurrentTokenBucketRateLimiter(long maxTokens, long refillPerSec) {
        this.maxTokens = maxTokens;
        this.tokens = new AtomicLong(maxTokens);
        this.refillRate = refillPerSec;
        this.lastRefillTime = new AtomicLong(System.nanoTime());
    }

    public boolean tryConsume() {
        refill();
        while (true) {
            long current = tokens.get();
            if (current <= 0) return false;
            if (tokens.compareAndSet(current, current - 1)) return true;
        }
    }

    private void refill() {
        long now = System.nanoTime();
        long last = lastRefillTime.get();
        long elapsed = (now - last) / 1_000_000_000L;
        if (elapsed > 0 && lastRefillTime.compareAndSet(last, now)) {
            long newTokens = Math.min(maxTokens, tokens.get() + elapsed * refillRate);
            tokens.set(newTokens);
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem30_ConcurrentTokenBucketRateLimiter rl = new Problem30_ConcurrentTokenBucketRateLimiter(5, 2);
        AtomicInteger allowed = new AtomicInteger(0);
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> { if (rl.tryConsume()) allowed.incrementAndGet(); });
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("Allowed: " + allowed.get() + " out of 10 requests");
    }
}
