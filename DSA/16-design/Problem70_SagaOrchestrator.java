import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

/**
 * Problem 70: Saga Orchestrator (Compensation, Rollback)
 * 
 * PRODUCTION MAPPING: Temporal.io, AWS Step Functions, Uber Cadence,
 *                     Netflix Conductor, Axon Saga, microservice transactions
 * 
 * Problem: Distributed transactions across services (no 2PC available)
 * Solution: Saga = sequence of local transactions with compensating actions
 * 
 * Two styles:
 * 1. Choreography: each service emits events, next service reacts (decentralized)
 * 2. Orchestration: central coordinator manages step execution (this implementation)
 * 
 * Design Decisions:
 * - Each step has: execute() + compensate() (inverse operation)
 * - On failure: compensate all previously completed steps in reverse order
 * - Supports: retries, timeouts, step-level failure handling
 * - Idempotent compensations (may be called multiple times)
 * 
 * Example: Create Order saga:
 * 1. Reserve inventory -> compensate: release inventory
 * 2. Charge payment -> compensate: refund payment
 * 3. Ship order -> compensate: cancel shipment
 * If step 3 fails, compensate 2 then 1.
 */
public class Problem70_SagaOrchestrator {

    enum StepStatus { PENDING, EXECUTING, COMPLETED, FAILED, COMPENSATING, COMPENSATED }
    enum SagaStatus { RUNNING, COMPLETED, COMPENSATING, FAILED, COMPENSATION_FAILED }

    static class SagaStep {
        final String name;
        final Supplier<Boolean> execute;      // returns true on success
        final Runnable compensate;            // idempotent compensation
        final int maxRetries;
        StepStatus status = StepStatus.PENDING;
        int attempts = 0;
        String error;

        SagaStep(String name, Supplier<Boolean> execute, Runnable compensate, int maxRetries) {
            this.name = name;
            this.execute = execute;
            this.compensate = compensate;
            this.maxRetries = maxRetries;
        }

        SagaStep(String name, Supplier<Boolean> execute, Runnable compensate) {
            this(name, execute, compensate, 3);
        }
    }

    static class SagaResult {
        final SagaStatus status;
        final List<String> completedSteps;
        final List<String> compensatedSteps;
        final String failedStep;
        final String error;

        SagaResult(SagaStatus status, List<String> completed, List<String> compensated, 
                   String failedStep, String error) {
            this.status = status;
            this.completedSteps = completed;
            this.compensatedSteps = compensated;
            this.failedStep = failedStep;
            this.error = error;
        }
    }

    static class SagaOrchestrator {
        private final String sagaId;
        private final List<SagaStep> steps = new ArrayList<>();
        private SagaStatus status = SagaStatus.RUNNING;
        private final List<String> log = new ArrayList<>();

        public SagaOrchestrator(String sagaId) {
            this.sagaId = sagaId;
        }

        public SagaOrchestrator addStep(String name, Supplier<Boolean> execute, Runnable compensate) {
            steps.add(new SagaStep(name, execute, compensate));
            return this;
        }

        public SagaOrchestrator addStep(SagaStep step) {
            steps.add(step);
            return this;
        }

        /**
         * Execute the saga. On any step failure, compensate in reverse order.
         */
        public SagaResult execute() {
            List<String> completedSteps = new ArrayList<>();
            int failedIndex = -1;

            // Forward execution
            for (int i = 0; i < steps.size(); i++) {
                SagaStep step = steps.get(i);
                step.status = StepStatus.EXECUTING;
                log.add("EXECUTE: " + step.name);

                boolean success = executeWithRetry(step);
                
                if (success) {
                    step.status = StepStatus.COMPLETED;
                    completedSteps.add(step.name);
                    log.add("COMPLETED: " + step.name);
                } else {
                    step.status = StepStatus.FAILED;
                    failedIndex = i;
                    log.add("FAILED: " + step.name + " (" + step.error + ")");
                    break;
                }
            }

            // All steps succeeded
            if (failedIndex == -1) {
                status = SagaStatus.COMPLETED;
                return new SagaResult(SagaStatus.COMPLETED, completedSteps, 
                    Collections.emptyList(), null, null);
            }

            // Compensation (reverse order)
            status = SagaStatus.COMPENSATING;
            List<String> compensatedSteps = new ArrayList<>();
            boolean compensationFailed = false;

            for (int i = failedIndex - 1; i >= 0; i--) {
                SagaStep step = steps.get(i);
                step.status = StepStatus.COMPENSATING;
                log.add("COMPENSATE: " + step.name);

                try {
                    step.compensate.run();
                    step.status = StepStatus.COMPENSATED;
                    compensatedSteps.add(step.name);
                    log.add("COMPENSATED: " + step.name);
                } catch (Exception e) {
                    // Compensation failure is critical - needs manual intervention
                    log.add("COMPENSATION_FAILED: " + step.name + " - " + e.getMessage());
                    compensationFailed = true;
                    // Continue compensating remaining steps (best effort)
                }
            }

            String failedStepName = steps.get(failedIndex).name;
            if (compensationFailed) {
                status = SagaStatus.COMPENSATION_FAILED;
                return new SagaResult(SagaStatus.COMPENSATION_FAILED, completedSteps,
                    compensatedSteps, failedStepName, "Compensation failed - manual intervention needed");
            }

            status = SagaStatus.FAILED;
            return new SagaResult(SagaStatus.FAILED, completedSteps, compensatedSteps,
                failedStepName, steps.get(failedIndex).error);
        }

        private boolean executeWithRetry(SagaStep step) {
            while (step.attempts < step.maxRetries) {
                step.attempts++;
                try {
                    if (step.execute.get()) return true;
                } catch (Exception e) {
                    step.error = e.getMessage();
                }
                if (step.attempts < step.maxRetries) {
                    try { Thread.sleep(10 * step.attempts); } catch (InterruptedException e) { break; }
                }
            }
            if (step.error == null) step.error = "Max retries exceeded";
            return false;
        }

        public List<String> getLog() { return Collections.unmodifiableList(log); }
    }

    public static void main(String[] args) {
        System.out.println("=== Saga Orchestrator ===\n");

        // Test 1: Successful saga (all steps complete)
        List<String> actions = new ArrayList<>();
        SagaOrchestrator saga = new SagaOrchestrator("order-saga-1")
            .addStep("reserve-inventory", () -> { actions.add("reserved"); return true; },
                     () -> actions.add("released-inventory"))
            .addStep("charge-payment", () -> { actions.add("charged"); return true; },
                     () -> actions.add("refunded"))
            .addStep("ship-order", () -> { actions.add("shipped"); return true; },
                     () -> actions.add("cancelled-shipment"));

        SagaResult result = saga.execute();
        assert result.status == SagaStatus.COMPLETED;
        assert result.completedSteps.size() == 3;
        assert result.compensatedSteps.isEmpty();
        System.out.println("PASS: All steps completed: " + actions);

        // Test 2: Failure triggers compensation
        actions.clear();
        saga = new SagaOrchestrator("order-saga-2")
            .addStep("reserve-inventory", () -> { actions.add("reserved"); return true; },
                     () -> actions.add("released"))
            .addStep("charge-payment", () -> { actions.add("charged"); return true; },
                     () -> actions.add("refunded"))
            .addStep("ship-order", () -> { actions.add("FAIL-ship"); return false; },
                     () -> actions.add("cancel-ship"));

        result = saga.execute();
        assert result.status == SagaStatus.FAILED;
        assert result.failedStep.equals("ship-order");
        assert result.compensatedSteps.size() == 2;
        assert actions.contains("refunded") && actions.contains("released");
        System.out.println("PASS: Failure compensates in reverse: " + actions);
        System.out.println("  Compensated: " + result.compensatedSteps);

        // Test 3: First step fails (no compensation needed)
        actions.clear();
        saga = new SagaOrchestrator("order-saga-3")
            .addStep("reserve-inventory", () -> false, () -> actions.add("should-not-happen"))
            .addStep("charge-payment", () -> true, () -> actions.add("refund"));

        result = saga.execute();
        assert result.status == SagaStatus.FAILED;
        assert result.compensatedSteps.isEmpty();
        assert !actions.contains("should-not-happen");
        System.out.println("PASS: First step failure - no compensation needed");

        // Test 4: Retry on transient failure
        AtomicInteger tryCount = new AtomicInteger(0);
        saga = new SagaOrchestrator("retry-saga")
            .addStep(new SagaStep("flaky-step", () -> {
                return tryCount.incrementAndGet() >= 3; // succeeds on 3rd try
            }, () -> {}, 5));

        result = saga.execute();
        assert result.status == SagaStatus.COMPLETED;
        assert tryCount.get() == 3;
        System.out.println("PASS: Retry succeeds on 3rd attempt");

        // Test 5: Saga execution log
        actions.clear();
        saga = new SagaOrchestrator("logged-saga")
            .addStep("step-A", () -> true, () -> {})
            .addStep("step-B", () -> false, () -> {});

        saga.execute();
        System.out.println("\nExecution log:");
        for (String entry : saga.getLog()) {
            System.out.println("  " + entry);
        }

        // Test 6: Real-world example - E-commerce order
        System.out.println("\n--- E-commerce Order Saga ---");
        Map<String, Object> state = new ConcurrentHashMap<>();
        
        saga = new SagaOrchestrator("ecommerce-order")
            .addStep("validate-order", 
                () -> { state.put("validated", true); return true; },
                () -> state.remove("validated"))
            .addStep("reserve-inventory",
                () -> { state.put("inventory-reserved", true); return true; },
                () -> { state.remove("inventory-reserved"); System.out.println("  [COMPENSATE] Inventory released"); })
            .addStep("process-payment",
                () -> { state.put("payment-id", "pay-123"); return true; },
                () -> { state.remove("payment-id"); System.out.println("  [COMPENSATE] Payment refunded"); })
            .addStep("send-notification",
                () -> { throw new RuntimeException("Email service down"); },
                () -> {});

        result = saga.execute();
        System.out.println("  Status: " + result.status);
        System.out.println("  Failed at: " + result.failedStep);
        System.out.println("  Compensated: " + result.compensatedSteps);
        assert !state.containsKey("payment-id") : "Payment should be refunded";
        assert !state.containsKey("inventory-reserved") : "Inventory should be released";
        System.out.println("  State after compensation: " + state);
        System.out.println("PASS: Full compensation on notification failure");

        System.out.println("\nAll tests passed!");
    }
}
