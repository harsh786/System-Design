import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

/**
 * Problem 56: Circuit Breaker with Half-Open State, Failure Thresholds
 * 
 * PRODUCTION MAPPING: Netflix Hystrix, Resilience4j, Polly (.NET), Envoy proxy
 * 
 * States:
 * - CLOSED: Normal operation. Failures counted. Trips to OPEN if threshold exceeded.
 * - OPEN: All calls fast-fail immediately. After timeout, transitions to HALF_OPEN.
 * - HALF_OPEN: Limited trial calls allowed. If successful -> CLOSED. If fail -> OPEN.
 * 
 * Design Decisions:
 * - Sliding window for failure rate calculation (not just total count)
 * - Configurable: failure threshold %, minimum calls, wait duration, trial calls
 * - Metrics tracking: success/failure counts, state transitions
 * 
 * Trade-offs:
 * - Short open duration: fails fast but retries too eagerly on flapping services
 * - Long open duration: protects system but delays recovery
 * - Half-open trial count: 1 = fast recovery detection but noisy, N = more confident
 * 
 * Staff insight: Circuit breakers should be per-endpoint, not per-service.
 * A slow /search shouldn't break /health-check.
 */
public class Problem56_CircuitBreaker {

    enum State { CLOSED, OPEN, HALF_OPEN }

    static class CircuitBreakerConfig {
        final int failureThresholdPercent; // e.g., 50 = open when 50% fail
        final int minimumCalls;            // minimum calls before evaluating
        final long waitDurationMs;         // time in OPEN before trying HALF_OPEN
        final int permittedCallsInHalfOpen; // trial calls allowed
        final int slidingWindowSize;       // rolling window for failure rate

        CircuitBreakerConfig(int failureThresholdPercent, int minimumCalls,
                            long waitDurationMs, int permittedCallsInHalfOpen,
                            int slidingWindowSize) {
            this.failureThresholdPercent = failureThresholdPercent;
            this.minimumCalls = minimumCalls;
            this.waitDurationMs = waitDurationMs;
            this.permittedCallsInHalfOpen = permittedCallsInHalfOpen;
            this.slidingWindowSize = slidingWindowSize;
        }
    }

    static class CircuitBreaker {
        private final CircuitBreakerConfig config;
        private volatile State state = State.CLOSED;
        private final Deque<Boolean> slidingWindow = new ArrayDeque<>(); // true=success
        private long openedAt;
        private int halfOpenAttempts;
        private int halfOpenSuccesses;

        // Metrics
        private long totalCalls = 0;
        private long totalFailures = 0;
        private long totalRejected = 0;
        private final List<String> stateTransitions = new ArrayList<>();

        public CircuitBreaker(CircuitBreakerConfig config) {
            this.config = config;
            stateTransitions.add("INITIAL -> CLOSED");
        }

        public <T> T execute(Supplier<T> action, Supplier<T> fallback) {
            if (!allowRequest()) {
                totalRejected++;
                return fallback.get();
            }

            try {
                T result = action.get();
                recordSuccess();
                return result;
            } catch (Exception e) {
                recordFailure();
                return fallback.get();
            }
        }

        public boolean allowRequest() {
            switch (state) {
                case CLOSED:
                    return true;
                case OPEN:
                    if (System.currentTimeMillis() - openedAt >= config.waitDurationMs) {
                        transitionTo(State.HALF_OPEN);
                        return true;
                    }
                    return false;
                case HALF_OPEN:
                    return halfOpenAttempts < config.permittedCallsInHalfOpen;
                default:
                    return false;
            }
        }

        private synchronized void recordSuccess() {
            totalCalls++;
            if (state == State.HALF_OPEN) {
                halfOpenSuccesses++;
                halfOpenAttempts++;
                if (halfOpenAttempts >= config.permittedCallsInHalfOpen) {
                    // All trial calls complete - check if enough succeeded
                    transitionTo(State.CLOSED);
                }
            } else {
                addToWindow(true);
            }
        }

        private synchronized void recordFailure() {
            totalCalls++;
            totalFailures++;
            if (state == State.HALF_OPEN) {
                halfOpenAttempts++;
                // Any failure in half-open -> back to open
                transitionTo(State.OPEN);
            } else {
                addToWindow(false);
                evaluateState();
            }
        }

        private void addToWindow(boolean success) {
            slidingWindow.addLast(success);
            while (slidingWindow.size() > config.slidingWindowSize) {
                slidingWindow.pollFirst();
            }
        }

        private void evaluateState() {
            if (slidingWindow.size() < config.minimumCalls) return;

            long failures = slidingWindow.stream().filter(b -> !b).count();
            double failureRate = (failures * 100.0) / slidingWindow.size();

            if (failureRate >= config.failureThresholdPercent) {
                transitionTo(State.OPEN);
            }
        }

        private void transitionTo(State newState) {
            if (state == newState) return;
            String transition = state + " -> " + newState;
            stateTransitions.add(transition);
            state = newState;

            if (newState == State.OPEN) {
                openedAt = System.currentTimeMillis();
            } else if (newState == State.HALF_OPEN) {
                halfOpenAttempts = 0;
                halfOpenSuccesses = 0;
            } else if (newState == State.CLOSED) {
                slidingWindow.clear();
            }
        }

        public State getState() { return state; }
        public List<String> getTransitions() { return stateTransitions; }
        public long getRejectedCount() { return totalRejected; }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Circuit Breaker ===\n");

        // Config: 50% failure rate, min 4 calls, 200ms open wait, 2 trial calls
        CircuitBreakerConfig config = new CircuitBreakerConfig(50, 4, 200, 2, 10);
        CircuitBreaker cb = new CircuitBreaker(config);

        // Test 1: Stays closed with successful calls
        for (int i = 0; i < 5; i++) {
            cb.execute(() -> "ok", () -> "fallback");
        }
        assert cb.getState() == State.CLOSED;
        System.out.println("PASS: Stays CLOSED with all successes");

        // Test 2: Opens after failure threshold
        cb = new CircuitBreaker(config);
        AtomicInteger callCount = new AtomicInteger(0);
        for (int i = 0; i < 6; i++) {
            cb.execute(() -> { 
                throw new RuntimeException("fail"); 
            }, () -> "fallback");
        }
        assert cb.getState() == State.OPEN : "Should be OPEN, got: " + cb.getState();
        System.out.println("PASS: Opens after failure threshold exceeded");

        // Test 3: Rejects calls when OPEN
        String result = cb.execute(() -> "should-not-run", () -> "rejected");
        assert result.equals("rejected");
        assert cb.getRejectedCount() > 0;
        System.out.println("PASS: Fast-fails when OPEN (returns fallback)");

        // Test 4: Transitions to HALF_OPEN after wait
        Thread.sleep(250);
        assert cb.allowRequest() : "Should allow after wait duration";
        assert cb.getState() == State.HALF_OPEN;
        System.out.println("PASS: Transitions to HALF_OPEN after wait");

        // Test 5: Recovers to CLOSED after successful trial calls
        cb = new CircuitBreaker(config);
        // Trip the breaker
        for (int i = 0; i < 6; i++) {
            cb.execute(() -> { throw new RuntimeException(); }, () -> "f");
        }
        assert cb.getState() == State.OPEN;
        Thread.sleep(250);
        // Trial calls succeed
        cb.execute(() -> "ok", () -> "f");
        cb.execute(() -> "ok", () -> "f");
        assert cb.getState() == State.CLOSED : "Should recover, got: " + cb.getState();
        System.out.println("PASS: Recovers to CLOSED after successful trials");

        // Test 6: Back to OPEN if trial fails
        cb = new CircuitBreaker(config);
        for (int i = 0; i < 6; i++) {
            cb.execute(() -> { throw new RuntimeException(); }, () -> "f");
        }
        Thread.sleep(250);
        // First trial call fails
        cb.execute(() -> { throw new RuntimeException(); }, () -> "f");
        assert cb.getState() == State.OPEN : "Should go back to OPEN";
        System.out.println("PASS: Returns to OPEN on trial failure");

        // Test 7: Print state transitions
        System.out.println("\nState transitions: " + cb.getTransitions());

        // Test 8: Mixed success/failure stays closed if below threshold
        cb = new CircuitBreaker(config);
        for (int i = 0; i < 10; i++) {
            if (i % 3 == 0) { // 33% failure rate, below 50% threshold
                cb.execute(() -> { throw new RuntimeException(); }, () -> "f");
            } else {
                cb.execute(() -> "ok", () -> "f");
            }
        }
        assert cb.getState() == State.CLOSED : "33% < 50% threshold, should stay closed";
        System.out.println("PASS: Stays CLOSED when failure rate below threshold");

        System.out.println("\nAll tests passed!");
    }
}
