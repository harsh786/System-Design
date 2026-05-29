import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 54: Backpressure Controller
 * 
 * Production Relevance:
 * - Prevents OOM when producer outpaces consumer (e.g., Kafka consumer lag, gRPC flow control)
 * - Reactive Streams specification (Project Reactor, RxJava) built around backpressure
 * - TCP flow control (sliding window) is backpressure at transport layer
 * - Without it: unbounded queues -> memory exhaustion -> cascading failures
 * 
 * Architect Considerations:
 * - Strategies: drop, buffer (bounded), throttle producer, sample
 * - Token bucket / credit-based flow control for rate limiting
 * - Must propagate backpressure upstream through entire pipeline
 */
public class Problem54_BackpressureController {

    enum BackpressureStrategy { DROP_NEWEST, DROP_OLDEST, BLOCK, THROTTLE }

    static class BackpressureBuffer<T> {
        private final int capacity;
        private final Deque<T> buffer;
        private final BackpressureStrategy strategy;
        private final AtomicLong dropped = new AtomicLong(0);
        private final AtomicLong processed = new AtomicLong(0);
        // Credit-based flow control
        private final AtomicInteger credits;

        BackpressureBuffer(int capacity, BackpressureStrategy strategy) {
            this.capacity = capacity;
            this.buffer = new ArrayDeque<>(capacity);
            this.strategy = strategy;
            this.credits = new AtomicInteger(capacity);
        }

        public synchronized boolean offer(T item) {
            if (buffer.size() >= capacity) {
                switch (strategy) {
                    case DROP_NEWEST:
                        dropped.incrementAndGet();
                        return false;
                    case DROP_OLDEST:
                        buffer.pollFirst();
                        dropped.incrementAndGet();
                        buffer.addLast(item);
                        return true;
                    case BLOCK:
                        try { wait(100); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                        if (buffer.size() >= capacity) { dropped.incrementAndGet(); return false; }
                        buffer.addLast(item);
                        return true;
                    case THROTTLE:
                        if (credits.get() <= 0) { dropped.incrementAndGet(); return false; }
                        break;
                }
            }
            buffer.addLast(item);
            credits.decrementAndGet();
            return true;
        }

        public synchronized T poll() {
            T item = buffer.pollFirst();
            if (item != null) {
                processed.incrementAndGet();
                credits.incrementAndGet();
                notifyAll();
            }
            return item;
        }

        public int size() { return buffer.size(); }
        public long getDropped() { return dropped.get(); }
        public long getProcessed() { return processed.get(); }
        public int getAvailableCredits() { return credits.get(); }
    }

    // Adaptive backpressure: adjusts rate based on consumer throughput
    static class AdaptiveRateController {
        private double currentRate; // items per second allowed
        private final double maxRate;
        private final double minRate;
        private long lastAdjustment;
        private int successCount;
        private int failureCount;

        AdaptiveRateController(double maxRate) {
            this.maxRate = maxRate;
            this.minRate = maxRate * 0.01;
            this.currentRate = maxRate;
            this.lastAdjustment = System.currentTimeMillis();
        }

        public void recordSuccess() { successCount++; adjust(); }
        public void recordFailure() { failureCount++; adjust(); }

        private void adjust() {
            long now = System.currentTimeMillis();
            if (now - lastAdjustment < 1000) return;
            double failureRatio = (double) failureCount / Math.max(1, successCount + failureCount);
            if (failureRatio > 0.1) {
                currentRate = Math.max(minRate, currentRate * 0.5); // Multiplicative decrease
            } else {
                currentRate = Math.min(maxRate, currentRate + maxRate * 0.1); // Additive increase
            }
            successCount = 0;
            failureCount = 0;
            lastAdjustment = now;
        }

        public double getCurrentRate() { return currentRate; }
    }

    public static void main(String[] args) {
        System.out.println("=== Backpressure Controller ===\n");

        // Test DROP_NEWEST strategy
        BackpressureBuffer<String> dropNewest = new BackpressureBuffer<>(5, BackpressureStrategy.DROP_NEWEST);
        for (int i = 0; i < 10; i++) {
            boolean accepted = dropNewest.offer("event-" + i);
            System.out.printf("Offer event-%d: %s (buffer size: %d)%n", i, accepted, dropNewest.size());
        }
        System.out.printf("Dropped: %d, Processed: %d%n%n", dropNewest.getDropped(), dropNewest.getProcessed());

        // Consume some, then offer more
        dropNewest.poll();
        dropNewest.poll();
        System.out.printf("After consuming 2: credits=%d, size=%d%n", dropNewest.getAvailableCredits(), dropNewest.size());

        // Test DROP_OLDEST strategy
        BackpressureBuffer<String> dropOldest = new BackpressureBuffer<>(3, BackpressureStrategy.DROP_OLDEST);
        for (int i = 0; i < 6; i++) dropOldest.offer("msg-" + i);
        System.out.printf("%nDROP_OLDEST buffer (cap=3): size=%d, dropped=%d%n", dropOldest.size(), dropOldest.getDropped());
        while (dropOldest.size() > 0) System.out.println("  Poll: " + dropOldest.poll());

        // Adaptive rate controller
        AdaptiveRateController arc = new AdaptiveRateController(1000);
        System.out.printf("%nAdaptive rate: %.0f/s%n", arc.getCurrentRate());
    }
}
