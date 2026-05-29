import java.util.*;

/**
 * Problem 56: Exponential Backoff with Priority
 * 
 * Production Relevance:
 * - Retry failed requests with increasing delay to avoid thundering herd
 * - Priority ensures critical retries happen before less important ones
 * - Used in HTTP clients, message queue consumers, distributed lock acquisition
 * - Jitter prevents synchronized retries across clients (correlated failures)
 * 
 * Architect Considerations:
 * - Base delay * 2^attempt + random jitter (full/equal/decorrelated jitter)
 * - Max backoff cap to prevent unbounded waits
 * - Priority-aware: critical retries get shorter backoff multipliers
 * - Circuit breaker integration: stop retrying after threshold
 */
public class Problem56_ExponentialBackoffWithPriority {

    static class RetryTask implements Comparable<RetryTask> {
        String id;
        int priority; // lower = higher priority
        int attempt;
        long nextRetryTime;
        int maxAttempts;
        String status;

        RetryTask(String id, int priority, int maxAttempts) {
            this.id = id; this.priority = priority; this.maxAttempts = maxAttempts;
        }

        @Override
        public int compareTo(RetryTask other) {
            if (this.nextRetryTime != other.nextRetryTime)
                return Long.compare(this.nextRetryTime, other.nextRetryTime);
            return Integer.compare(this.priority, other.priority);
        }
    }

    enum JitterStrategy { FULL, EQUAL, DECORRELATED }

    static class PriorityBackoffScheduler {
        private final PriorityQueue<RetryTask> retryQueue = new PriorityQueue<>();
        private final long baseDelayMs;
        private final long maxDelayMs;
        private final JitterStrategy jitter;
        private final Random random = new Random(42);
        private long currentTime = 0;
        private final List<String> log = new ArrayList<>();

        PriorityBackoffScheduler(long baseDelayMs, long maxDelayMs, JitterStrategy jitter) {
            this.baseDelayMs = baseDelayMs; this.maxDelayMs = maxDelayMs; this.jitter = jitter;
        }

        void scheduleRetry(RetryTask task) {
            task.attempt++;
            if (task.attempt > task.maxAttempts) {
                task.status = "EXHAUSTED";
                log.add(String.format("  %s: max retries exhausted after %d attempts", task.id, task.maxAttempts));
                return;
            }

            // Priority-adjusted backoff: higher priority = shorter backoff
            double priorityMultiplier = 1.0 + (task.priority - 1) * 0.5; // P1=1x, P2=1.5x, P3=2x
            long exponentialDelay = (long) (baseDelayMs * Math.pow(2, task.attempt - 1) * priorityMultiplier);
            long cappedDelay = Math.min(exponentialDelay, maxDelayMs);
            long actualDelay = applyJitter(cappedDelay);

            task.nextRetryTime = currentTime + actualDelay;
            retryQueue.offer(task);
            log.add(String.format("  %s (P%d): attempt %d, backoff %dms (next at t=%d)",
                    task.id, task.priority, task.attempt, actualDelay, task.nextRetryTime));
        }

        private long applyJitter(long delay) {
            switch (jitter) {
                case FULL: return (long) (random.nextDouble() * delay);
                case EQUAL: return delay / 2 + (long) (random.nextDouble() * delay / 2);
                case DECORRELATED: return (long) (baseDelayMs + random.nextDouble() * (delay * 3 - baseDelayMs));
                default: return delay;
            }
        }

        RetryTask getNextReady() {
            if (retryQueue.isEmpty() || retryQueue.peek().nextRetryTime > currentTime) return null;
            return retryQueue.poll();
        }

        void advanceTime(long ms) { currentTime += ms; }
        long getCurrentTime() { return currentTime; }
        void printLog() { log.forEach(System.out::println); }
    }

    public static void main(String[] args) {
        System.out.println("=== Exponential Backoff with Priority ===\n");

        PriorityBackoffScheduler scheduler = new PriorityBackoffScheduler(100, 10000, JitterStrategy.EQUAL);

        RetryTask critical = new RetryTask("payment-retry", 1, 5);
        RetryTask normal = new RetryTask("email-send", 2, 3);
        RetryTask low = new RetryTask("analytics-push", 3, 3);

        // All fail at same time, schedule retries
        System.out.println("Scheduling retries:");
        scheduler.scheduleRetry(critical);
        scheduler.scheduleRetry(normal);
        scheduler.scheduleRetry(low);

        // Simulate: all fail again on retry
        for (int round = 0; round < 3; round++) {
            scheduler.advanceTime(5000); // advance 5s
            RetryTask ready;
            while ((ready = scheduler.getNextReady()) != null) {
                scheduler.scheduleRetry(ready); // fails again
            }
        }

        scheduler.printLog();
    }
}
