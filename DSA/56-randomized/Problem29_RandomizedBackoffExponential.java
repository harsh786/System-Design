import java.util.*;

public class Problem29_RandomizedBackoffExponential {
    // Exponential backoff with jitter for retry logic
    static Random rand = new Random();

    public static long calculateBackoff(int attempt, long baseMs, long maxMs) {
        long exponential = (long)(baseMs * Math.pow(2, attempt));
        long capped = Math.min(exponential, maxMs);
        // Full jitter: random between 0 and capped
        return (long)(rand.nextDouble() * capped);
    }

    public static boolean retryWithBackoff(int maxRetries) throws InterruptedException {
        for (int i = 0; i < maxRetries; i++) {
            long wait = calculateBackoff(i, 100, 10000);
            System.out.println("Attempt " + (i+1) + ", waiting " + wait + "ms");
            // Thread.sleep(wait); // commented for demo
            if (rand.nextDouble() < 0.3) { System.out.println("Success!"); return true; }
        }
        return false;
    }

    public static void main(String[] args) throws InterruptedException {
        retryWithBackoff(5);
    }
}
