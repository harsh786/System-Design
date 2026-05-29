import java.util.*;

/**
 * Problem 55: Weighted Fair Queue
 * 
 * Production Relevance:
 * - Network QoS: allocate bandwidth proportional to weight (WFQ, DRR)
 * - Multi-tenant resource allocation: tenant A gets 3x resources of tenant B
 * - Used in Linux tc (traffic control), Kubernetes resource quotas, thread pool scheduling
 * - Guarantees proportional fairness while maintaining work-conserving property
 * 
 * Architect Considerations:
 * - Virtual time / deficit round robin for O(1) scheduling decisions
 * - Work-conserving: unused capacity redistributed to active queues
 * - Burst tolerance: allow short bursts above fair share
 */
public class Problem55_WeightedFairQueue {

    static class Flow {
        String id;
        int weight;
        Queue<String> packets = new LinkedList<>();
        long virtualFinishTime = 0;
        int totalServed = 0;

        Flow(String id, int weight) { this.id = id; this.weight = weight; }
    }

    // Weighted Fair Queueing using virtual time
    static class WFQScheduler {
        Map<String, Flow> flows = new LinkedHashMap<>();
        long virtualTime = 0;
        int totalPacketsServed = 0;

        void addFlow(String id, int weight) { flows.put(id, new Flow(id, weight)); }

        void enqueue(String flowId, String packet) {
            Flow flow = flows.get(flowId);
            flow.packets.offer(packet);
            if (flow.packets.size() == 1) {
                // Calculate virtual finish time for head packet
                flow.virtualFinishTime = Math.max(virtualTime, flow.virtualFinishTime) + (1000 / flow.weight);
            }
        }

        // Dequeue: pick packet with smallest virtual finish time
        String dequeue() {
            Flow selected = null;
            for (Flow f : flows.values()) {
                if (!f.packets.isEmpty()) {
                    if (selected == null || f.virtualFinishTime < selected.virtualFinishTime) {
                        selected = f;
                    }
                }
            }
            if (selected == null) return null;

            String packet = selected.packets.poll();
            virtualTime = selected.virtualFinishTime;
            selected.totalServed++;
            totalPacketsServed++;

            // Update virtual finish time for next packet
            if (!selected.packets.isEmpty()) {
                selected.virtualFinishTime = virtualTime + (1000 / selected.weight);
            }
            return selected.id + ":" + packet;
        }

        void printFairness() {
            System.out.println("\nFairness analysis:");
            int totalWeight = flows.values().stream().mapToInt(f -> f.weight).sum();
            for (Flow f : flows.values()) {
                double expectedShare = (double) f.weight / totalWeight;
                double actualShare = (double) f.totalServed / Math.max(1, totalPacketsServed);
                System.out.printf("  %s: weight=%d, expected=%.1f%%, actual=%.1f%%, served=%d%n",
                        f.id, f.weight, expectedShare * 100, actualShare * 100, f.totalServed);
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Weighted Fair Queue ===\n");

        WFQScheduler scheduler = new WFQScheduler();
        scheduler.addFlow("premium", 5);   // 5x weight
        scheduler.addFlow("standard", 3);  // 3x weight
        scheduler.addFlow("basic", 1);     // 1x weight

        // Enqueue packets (all flows have equal backlog)
        for (int i = 0; i < 20; i++) {
            scheduler.enqueue("premium", "pkt-" + i);
            scheduler.enqueue("standard", "pkt-" + i);
            scheduler.enqueue("basic", "pkt-" + i);
        }

        // Dequeue and observe fairness
        System.out.println("Dequeue order (first 18):");
        for (int i = 0; i < 18; i++) {
            String result = scheduler.dequeue();
            System.out.printf("  %2d: %s%n", i + 1, result);
        }

        // Continue to drain
        while (scheduler.dequeue() != null) {}
        scheduler.printFairness();
    }
}
