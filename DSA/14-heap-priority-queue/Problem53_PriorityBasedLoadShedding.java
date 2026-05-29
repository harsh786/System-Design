import java.util.*;

/**
 * Problem 53: Priority-based Load Shedding
 * 
 * Production Relevance:
 * - When system is overloaded, shed low-priority requests to protect high-priority ones
 * - Used in API gateways (shed analytics before payments), CDNs, real-time systems
 * - Google's approach: criticality levels (CRITICAL_PLUS, CRITICAL, SHEDDABLE_PLUS, SHEDDABLE)
 * - Without load shedding: entire system degrades uniformly, worst outcome for all
 * 
 * Architect Considerations:
 * - Shedding decision must be O(1) - can't afford expensive computation during overload
 * - Progressive shedding: shed lowest priority first, escalate if still overloaded
 * - Must shed early (at edge/load balancer) not deep in the call stack
 */
public class Problem53_PriorityBasedLoadShedding {

    enum Criticality { CRITICAL_PLUS, CRITICAL, SHEDDABLE_PLUS, SHEDDABLE }

    static class Request {
        String id;
        Criticality criticality;
        long arrivalTime;
        int processingTimeMs;

        Request(String id, Criticality crit, int processingMs) {
            this.id = id; this.criticality = crit;
            this.processingTimeMs = processingMs; this.arrivalTime = System.nanoTime();
        }
    }

    static class LoadShedder {
        private final int maxConcurrency;
        private int currentLoad = 0;
        private final double[] sheddingThresholds; // per criticality level
        private final Map<Criticality, Integer> admitted = new EnumMap<>(Criticality.class);
        private final Map<Criticality, Integer> shed = new EnumMap<>(Criticality.class);
        private final PriorityQueue<Request> queue;

        LoadShedder(int maxConcurrency) {
            this.maxConcurrency = maxConcurrency;
            // Start shedding SHEDDABLE at 70%, SHEDDABLE_PLUS at 85%, CRITICAL at 95%
            this.sheddingThresholds = new double[]{1.0, 0.95, 0.85, 0.70};
            this.queue = new PriorityQueue<>(Comparator.comparingInt(r -> r.criticality.ordinal()));
            for (Criticality c : Criticality.values()) { admitted.put(c, 0); shed.put(c, 0); }
        }

        boolean shouldShed(Request request) {
            double loadFactor = (double) currentLoad / maxConcurrency;
            double threshold = sheddingThresholds[request.criticality.ordinal()];
            return loadFactor >= threshold;
        }

        boolean admit(Request request) {
            if (shouldShed(request)) {
                shed.merge(request.criticality, 1, Integer::sum);
                return false;
            }
            currentLoad++;
            admitted.merge(request.criticality, 1, Integer::sum);
            queue.offer(request);
            return true;
        }

        void complete() {
            if (!queue.isEmpty()) {
                queue.poll();
                currentLoad--;
            }
        }

        double getLoadFactor() { return (double) currentLoad / maxConcurrency; }

        void printStats() {
            System.out.println("  Admitted: " + admitted);
            System.out.println("  Shed:     " + shed);
            int totalAdmitted = admitted.values().stream().mapToInt(i -> i).sum();
            int totalShed = shed.values().stream().mapToInt(i -> i).sum();
            System.out.printf("  Total: %d admitted, %d shed (%.1f%% shed rate)%n",
                    totalAdmitted, totalShed, 100.0 * totalShed / (totalAdmitted + totalShed));
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Priority-based Load Shedding ===\n");

        LoadShedder shedder = new LoadShedder(10); // max 10 concurrent

        // Simulate burst of requests
        Request[] burst = {
            new Request("pay-1", Criticality.CRITICAL_PLUS, 100),
            new Request("pay-2", Criticality.CRITICAL_PLUS, 100),
            new Request("api-1", Criticality.CRITICAL, 50),
            new Request("api-2", Criticality.CRITICAL, 50),
            new Request("api-3", Criticality.CRITICAL, 50),
            new Request("analytics-1", Criticality.SHEDDABLE_PLUS, 200),
            new Request("analytics-2", Criticality.SHEDDABLE_PLUS, 200),
            new Request("log-1", Criticality.SHEDDABLE, 300),
            new Request("log-2", Criticality.SHEDDABLE, 300),
            new Request("log-3", Criticality.SHEDDABLE, 300),
            new Request("pay-3", Criticality.CRITICAL_PLUS, 100),
            new Request("log-4", Criticality.SHEDDABLE, 300),
            new Request("api-4", Criticality.CRITICAL, 50),
        };

        for (Request r : burst) {
            boolean accepted = shedder.admit(r);
            System.out.printf("  %-15s %-16s load=%.0f%% -> %s%n",
                    r.id, r.criticality, shedder.getLoadFactor() * 100,
                    accepted ? "ADMITTED" : "SHED");
        }

        System.out.println("\nFinal stats:");
        shedder.printStats();
    }
}
