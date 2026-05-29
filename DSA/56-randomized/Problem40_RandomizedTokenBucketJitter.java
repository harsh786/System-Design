import java.util.*;

public class Problem40_RandomizedTokenBucketJitter {
    // Token bucket with jittered refill for distributed systems
    double tokens;
    double maxTokens;
    long lastRefill;
    double refillRate;
    Random rand = new Random();

    public Problem40_RandomizedTokenBucketJitter(double max, double rate) {
        maxTokens = max; tokens = max; refillRate = rate; lastRefill = System.currentTimeMillis();
    }

    public synchronized boolean tryConsume() {
        refill();
        if (tokens >= 1) { tokens--; return true; }
        return false;
    }

    void refill() {
        long now = System.currentTimeMillis();
        double elapsed = (now - lastRefill) / 1000.0;
        // Add jitter: ±10% to refill timing
        double jitter = 0.9 + rand.nextDouble() * 0.2;
        tokens = Math.min(maxTokens, tokens + elapsed * refillRate * jitter);
        lastRefill = now;
    }

    public static void main(String[] args) {
        Problem40_RandomizedTokenBucketJitter tb = new Problem40_RandomizedTokenBucketJitter(5, 2);
        for (int i = 0; i < 8; i++) System.out.println("Request " + i + ": " + tb.tryConsume());
    }
}
