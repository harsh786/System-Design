import java.util.*;

/**
 * Problem 54: SLA-Aware Request Prioritization
 * 
 * Production Relevance:
 * - Multi-tenant systems must honor SLA tiers (e.g., 99.99% for enterprise, 99% for free)
 * - Requests from premium tenants get priority during resource contention
 * - Used in cloud services, SaaS platforms, database connection pooling
 * - Dynamic priority: requests approaching SLA deadline get boosted
 * 
 * Architect Considerations:
 * - Static priority (tier-based) + dynamic priority (deadline proximity)
 * - Must ensure lower tiers still get service (fairness within priority)
 * - Track per-tenant SLA compliance in real-time to adjust priorities
 */
public class Problem54_SLAAwareRequestPrioritization {

    static class TenantSLA {
        String tenantId;
        String tier; // enterprise, business, free
        double targetLatencyP99Ms;
        double targetAvailability;
        int priorityWeight;

        TenantSLA(String tenantId, String tier, double p99, double avail, int weight) {
            this.tenantId = tenantId; this.tier = tier;
            this.targetLatencyP99Ms = p99; this.targetAvailability = avail; this.priorityWeight = weight;
        }
    }

    static class PrioritizedRequest {
        String requestId;
        String tenantId;
        long arrivalTime;
        long slaDeadline;
        double effectivePriority;

        PrioritizedRequest(String reqId, String tenantId, long arrival, long deadline) {
            this.requestId = reqId; this.tenantId = tenantId;
            this.arrivalTime = arrival; this.slaDeadline = deadline;
        }
    }

    static class SLAScheduler {
        Map<String, TenantSLA> slas = new HashMap<>();
        Map<String, List<Long>> tenantLatencies = new HashMap<>(); // for P99 tracking
        PriorityQueue<PrioritizedRequest> queue = new PriorityQueue<>(
                (a, b) -> Double.compare(b.effectivePriority, a.effectivePriority));
        long currentTime = 0;

        void registerSLA(TenantSLA sla) { slas.put(sla.tenantId, sla); }

        void submit(PrioritizedRequest request) {
            // Compute effective priority: base weight + urgency bonus
            TenantSLA sla = slas.get(request.tenantId);
            double basePriority = sla != null ? sla.priorityWeight : 1;
            // Urgency: higher priority as deadline approaches
            long timeToDeadline = request.slaDeadline - currentTime;
            double urgencyBonus = timeToDeadline <= 0 ? 100 : 50.0 / timeToDeadline;
            // SLA compliance pressure: boost if tenant is close to violating SLA
            double complianceBonus = getCompliancePressure(request.tenantId);
            request.effectivePriority = basePriority + urgencyBonus + complianceBonus;
            queue.offer(request);
        }

        private double getCompliancePressure(String tenantId) {
            List<Long> latencies = tenantLatencies.getOrDefault(tenantId, List.of());
            if (latencies.size() < 10) return 0;
            TenantSLA sla = slas.get(tenantId);
            if (sla == null) return 0;
            // Check if current P99 is close to SLA target
            List<Long> sorted = new ArrayList<>(latencies);
            Collections.sort(sorted);
            long currentP99 = sorted.get((int)(sorted.size() * 0.99));
            double ratio = (double) currentP99 / sla.targetLatencyP99Ms;
            return ratio > 0.8 ? (ratio - 0.8) * 50 : 0; // Boost when > 80% of SLA target
        }

        PrioritizedRequest next() {
            PrioritizedRequest req = queue.poll();
            if (req != null) currentTime += 10; // simulate processing
            return req;
        }

        void recordLatency(String tenantId, long latencyMs) {
            tenantLatencies.computeIfAbsent(tenantId, k -> new ArrayList<>()).add(latencyMs);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== SLA-Aware Request Prioritization ===\n");

        SLAScheduler scheduler = new SLAScheduler();
        scheduler.registerSLA(new TenantSLA("enterprise-1", "enterprise", 50, 99.99, 100));
        scheduler.registerSLA(new TenantSLA("business-1", "business", 200, 99.9, 50));
        scheduler.registerSLA(new TenantSLA("free-1", "free", 1000, 99.0, 10));

        // Submit requests with different priorities
        scheduler.submit(new PrioritizedRequest("r1", "free-1", 0, 1000));
        scheduler.submit(new PrioritizedRequest("r2", "enterprise-1", 0, 50));
        scheduler.submit(new PrioritizedRequest("r3", "business-1", 0, 200));
        scheduler.submit(new PrioritizedRequest("r4", "enterprise-1", 0, 30)); // urgent!
        scheduler.submit(new PrioritizedRequest("r5", "free-1", 0, 500));

        System.out.println("Processing order (highest priority first):");
        PrioritizedRequest req;
        while ((req = scheduler.next()) != null) {
            TenantSLA sla = scheduler.slas.get(req.tenantId);
            System.out.printf("  %s [%s/%s] priority=%.1f deadline=%d%n",
                    req.requestId, req.tenantId, sla.tier, req.effectivePriority, req.slaDeadline);
        }
    }
}
