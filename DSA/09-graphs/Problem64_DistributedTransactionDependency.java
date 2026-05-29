import java.util.*;

/**
 * Problem 64: Distributed Transaction Dependency
 * 
 * Production Relevance:
 * - Saga pattern: sequence of local transactions with compensating actions on failure
 * - Must track which saga steps completed to know what compensations to run
 * - Orchestrator vs choreography patterns modeled as DAG
 * - Used in e-commerce (order->payment->inventory->shipping)
 * 
 * Architect Considerations:
 * - Forward recovery (retry) vs backward recovery (compensate) decision
 * - Partial failures: some steps succeed, some fail, some timeout
 * - Idempotent steps essential for retry safety
 * - Timeout handling: step may have succeeded but acknowledgement lost
 */
public class Problem64_DistributedTransactionDependency {

    enum StepStatus { PENDING, RUNNING, COMPLETED, FAILED, COMPENSATED }

    static class SagaStep {
        String id;
        String action;
        String compensation;
        List<String> dependsOn;
        StepStatus status = StepStatus.PENDING;
        int maxRetries;

        SagaStep(String id, String action, String compensation, int maxRetries, String... deps) {
            this.id = id; this.action = action; this.compensation = compensation;
            this.maxRetries = maxRetries; this.dependsOn = Arrays.asList(deps);
        }
    }

    static class SagaOrchestrator {
        Map<String, SagaStep> steps = new LinkedHashMap<>();
        List<String> executionLog = new ArrayList<>();
        boolean sagaCompleted = false;
        boolean sagaFailed = false;

        void addStep(SagaStep step) { steps.put(step.id, step); }

        // Execute saga forward
        void execute(Set<String> failingSteps) {
            List<String> order = topologicalOrder();

            for (String stepId : order) {
                SagaStep step = steps.get(stepId);
                // Check all dependencies completed
                boolean depsOk = step.dependsOn.stream()
                        .allMatch(d -> steps.get(d).status == StepStatus.COMPLETED);
                if (!depsOk) {
                    step.status = StepStatus.FAILED;
                    executionLog.add("SKIP " + stepId + " (dependency not met)");
                    continue;
                }

                step.status = StepStatus.RUNNING;
                if (failingSteps.contains(stepId)) {
                    step.status = StepStatus.FAILED;
                    executionLog.add("FAIL " + step.action);
                    // Trigger compensation for all completed steps (reverse order)
                    compensate(order, order.indexOf(stepId));
                    sagaFailed = true;
                    return;
                }
                step.status = StepStatus.COMPLETED;
                executionLog.add("OK   " + step.action);
            }
            sagaCompleted = true;
        }

        private void compensate(List<String> order, int failIndex) {
            executionLog.add("--- COMPENSATING ---");
            for (int i = failIndex - 1; i >= 0; i--) {
                SagaStep step = steps.get(order.get(i));
                if (step.status == StepStatus.COMPLETED) {
                    step.status = StepStatus.COMPENSATED;
                    executionLog.add("COMP " + step.compensation);
                }
            }
        }

        private List<String> topologicalOrder() {
            Map<String, Integer> inDeg = new HashMap<>();
            steps.keySet().forEach(s -> inDeg.put(s, 0));
            for (SagaStep s : steps.values()) {
                inDeg.put(s.id, s.dependsOn.size());
            }
            Queue<String> q = new LinkedList<>();
            inDeg.forEach((s, d) -> { if (d == 0) q.offer(s); });
            List<String> order = new ArrayList<>();
            while (!q.isEmpty()) {
                String s = q.poll();
                order.add(s);
                for (SagaStep step : steps.values()) {
                    if (step.dependsOn.contains(s)) {
                        if (inDeg.merge(step.id, -1, Integer::sum) == 0) q.offer(step.id);
                    }
                }
            }
            return order;
        }

        void printLog() { executionLog.forEach(l -> System.out.println("  " + l)); }
    }

    public static void main(String[] args) {
        System.out.println("=== Distributed Transaction Dependency (Saga) ===\n");

        // Successful saga
        System.out.println("--- Scenario 1: All steps succeed ---");
        SagaOrchestrator saga1 = new SagaOrchestrator();
        saga1.addStep(new SagaStep("reserve", "Reserve inventory", "Release inventory", 3));
        saga1.addStep(new SagaStep("payment", "Charge payment", "Refund payment", 3, "reserve"));
        saga1.addStep(new SagaStep("ship", "Create shipment", "Cancel shipment", 2, "payment"));
        saga1.addStep(new SagaStep("notify", "Send confirmation", "Send cancellation", 1, "ship"));
        saga1.execute(Set.of());
        saga1.printLog();
        System.out.println("  Status: " + (saga1.sagaCompleted ? "COMPLETED" : "FAILED"));

        // Failed saga with compensation
        System.out.println("\n--- Scenario 2: Payment fails -> compensate ---");
        SagaOrchestrator saga2 = new SagaOrchestrator();
        saga2.addStep(new SagaStep("reserve", "Reserve inventory", "Release inventory", 3));
        saga2.addStep(new SagaStep("payment", "Charge payment", "Refund payment", 3, "reserve"));
        saga2.addStep(new SagaStep("ship", "Create shipment", "Cancel shipment", 2, "payment"));
        saga2.execute(Set.of("payment")); // Payment fails
        saga2.printLog();
        System.out.println("  Status: " + (saga2.sagaFailed ? "FAILED + COMPENSATED" : "OK"));
    }
}
