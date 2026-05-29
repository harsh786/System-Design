import java.util.*;

/**
 * Problem 62: Resource Dependency Deadlock Detection
 * 
 * Production Relevance:
 * - Database deadlock detection (PostgreSQL, MySQL InnoDB) uses wait-for graphs
 * - Distributed deadlocks across microservices holding distributed locks
 * - OS resource allocation (Banker's algorithm for deadlock avoidance)
 * - Must detect AND resolve (victim selection for abort)
 * 
 * Architect Considerations:
 * - Wait-for graph: cycle = deadlock
 * - Victim selection: abort youngest transaction (least work lost)
 * - Timeout-based detection as fallback for distributed scenarios
 * - Prevention vs detection vs avoidance tradeoffs
 */
public class Problem62_ResourceDependencyDeadlockDetection {

    static class Transaction {
        String id;
        long startTime;
        Set<String> holdsLocks = new HashSet<>();
        String waitingFor; // resource waiting to acquire

        Transaction(String id, long startTime) { this.id = id; this.startTime = startTime; }
    }

    static class DeadlockDetector {
        Map<String, Transaction> transactions = new LinkedHashMap<>();
        Map<String, String> resourceOwners = new HashMap<>(); // resource -> txn holding it

        void registerTransaction(String txnId, long startTime) {
            transactions.put(txnId, new Transaction(txnId, startTime));
        }

        boolean acquireLock(String txnId, String resource) {
            String owner = resourceOwners.get(resource);
            if (owner == null || owner.equals(txnId)) {
                resourceOwners.put(resource, txnId);
                transactions.get(txnId).holdsLocks.add(resource);
                return true;
            }
            // Must wait
            transactions.get(txnId).waitingFor = resource;
            return false;
        }

        void releaseLock(String txnId, String resource) {
            resourceOwners.remove(resource);
            transactions.get(txnId).holdsLocks.remove(resource);
        }

        // Build wait-for graph and detect cycles
        List<List<String>> detectDeadlocks() {
            // Build wait-for graph: txn -> txn it's waiting for
            Map<String, String> waitFor = new HashMap<>();
            for (Transaction txn : transactions.values()) {
                if (txn.waitingFor != null) {
                    String blocker = resourceOwners.get(txn.waitingFor);
                    if (blocker != null && !blocker.equals(txn.id)) {
                        waitFor.put(txn.id, blocker);
                    }
                }
            }

            // Detect cycles using DFS
            List<List<String>> cycles = new ArrayList<>();
            Set<String> visited = new HashSet<>();
            for (String txn : waitFor.keySet()) {
                if (!visited.contains(txn)) {
                    List<String> path = new ArrayList<>();
                    Set<String> inPath = new HashSet<>();
                    String curr = txn;
                    while (curr != null && !inPath.contains(curr)) {
                        if (visited.contains(curr)) break;
                        path.add(curr);
                        inPath.add(curr);
                        curr = waitFor.get(curr);
                    }
                    if (curr != null && inPath.contains(curr)) {
                        int start = path.indexOf(curr);
                        List<String> cycle = new ArrayList<>(path.subList(start, path.size()));
                        cycle.add(curr);
                        cycles.add(cycle);
                    }
                    visited.addAll(inPath);
                }
            }
            return cycles;
        }

        // Resolve deadlock by aborting youngest transaction in cycle
        String resolveDeadlock(List<String> cycle) {
            String victim = null;
            long latestStart = Long.MIN_VALUE;
            for (String txnId : cycle) {
                Transaction txn = transactions.get(txnId);
                if (txn != null && txn.startTime > latestStart) {
                    latestStart = txn.startTime;
                    victim = txnId;
                }
            }
            if (victim != null) abort(victim);
            return victim;
        }

        void abort(String txnId) {
            Transaction txn = transactions.get(txnId);
            for (String res : new HashSet<>(txn.holdsLocks)) releaseLock(txnId, res);
            txn.waitingFor = null;
            transactions.remove(txnId);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Resource Dependency Deadlock Detection ===\n");

        DeadlockDetector detector = new DeadlockDetector();
        detector.registerTransaction("T1", 100);
        detector.registerTransaction("T2", 200);
        detector.registerTransaction("T3", 150);

        // T1 holds A, wants B
        detector.acquireLock("T1", "resourceA");
        // T2 holds B, wants C
        detector.acquireLock("T2", "resourceB");
        // T3 holds C, wants A
        detector.acquireLock("T3", "resourceC");

        // Now create deadlock
        detector.acquireLock("T1", "resourceB"); // T1 waits for T2
        detector.acquireLock("T2", "resourceC"); // T2 waits for T3
        detector.acquireLock("T3", "resourceA"); // T3 waits for T1 -> CYCLE!

        System.out.println("Lock state:");
        detector.transactions.forEach((id, txn) -> System.out.printf("  %s: holds=%s, waits=%s%n",
                id, txn.holdsLocks, txn.waitingFor));

        List<List<String>> deadlocks = detector.detectDeadlocks();
        System.out.println("\nDeadlocks detected: " + deadlocks.size());
        for (List<String> cycle : deadlocks) {
            System.out.println("  Cycle: " + String.join(" -> ", cycle));
            String victim = detector.resolveDeadlock(cycle);
            System.out.println("  Victim (youngest): " + victim);
        }
    }
}
