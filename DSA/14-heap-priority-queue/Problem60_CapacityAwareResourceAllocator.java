import java.util.*;

/**
 * Problem 60: Capacity-Aware Resource Allocator
 * 
 * Production Relevance:
 * - Cloud resource scheduling: bin-packing VMs onto physical hosts
 * - Kubernetes scheduler: place pods on nodes considering CPU, memory, GPU
 * - Database connection pool allocation across tenants
 * - Must maximize utilization while respecting per-resource capacity limits
 * 
 * Architect Considerations:
 * - Multi-dimensional bin packing (NP-hard, use heuristics: best-fit, first-fit)
 * - Priority heap: process highest-priority requests first, try to fit
 * - Fragmentation: small gaps across nodes that no request can fill
 * - Preemption: evict lower-priority allocations for critical requests
 */
public class Problem60_CapacityAwareResourceAllocator {

    static class ResourceRequest implements Comparable<ResourceRequest> {
        String id;
        int priority; // lower = higher priority
        int cpuNeeded;
        int memoryNeeded;
        long requestTime;

        ResourceRequest(String id, int priority, int cpu, int memory) {
            this.id = id; this.priority = priority;
            this.cpuNeeded = cpu; this.memoryNeeded = memory;
            this.requestTime = System.nanoTime();
        }

        @Override
        public int compareTo(ResourceRequest other) {
            return Integer.compare(this.priority, other.priority);
        }
    }

    static class Node {
        String id;
        int totalCpu, totalMemory;
        int usedCpu, usedMemory;
        List<ResourceRequest> allocations = new ArrayList<>();

        Node(String id, int cpu, int memory) {
            this.id = id; this.totalCpu = cpu; this.totalMemory = memory;
        }

        boolean canFit(ResourceRequest req) {
            return (totalCpu - usedCpu >= req.cpuNeeded) && (totalMemory - usedMemory >= req.memoryNeeded);
        }

        void allocate(ResourceRequest req) {
            usedCpu += req.cpuNeeded;
            usedMemory += req.memoryNeeded;
            allocations.add(req);
        }

        void deallocate(ResourceRequest req) {
            usedCpu -= req.cpuNeeded;
            usedMemory -= req.memoryNeeded;
            allocations.remove(req);
        }

        double utilization() {
            return ((double) usedCpu / totalCpu + (double) usedMemory / totalMemory) / 2;
        }

        // Score for best-fit: prefer nodes that would be most full after allocation
        double bestFitScore(ResourceRequest req) {
            double cpuAfter = (double) (usedCpu + req.cpuNeeded) / totalCpu;
            double memAfter = (double) (usedMemory + req.memoryNeeded) / totalMemory;
            return (cpuAfter + memAfter) / 2; // higher = tighter fit
        }
    }

    static class ResourceAllocator {
        List<Node> nodes = new ArrayList<>();
        PriorityQueue<ResourceRequest> pendingQueue = new PriorityQueue<>();
        List<String> log = new ArrayList<>();
        int allocated = 0, rejected = 0;

        void addNode(Node node) { nodes.add(node); }

        String allocate(ResourceRequest request) {
            // Best-fit decreasing: pick node that would be most full
            Node bestNode = null;
            double bestScore = -1;

            for (Node node : nodes) {
                if (node.canFit(request)) {
                    double score = node.bestFitScore(request);
                    if (score > bestScore) {
                        bestScore = score;
                        bestNode = node;
                    }
                }
            }

            if (bestNode != null) {
                bestNode.allocate(request);
                allocated++;
                log.add(String.format("  ALLOC %s -> %s (cpu=%d,mem=%d) node_util=%.0f%%",
                        request.id, bestNode.id, request.cpuNeeded, request.memoryNeeded, bestNode.utilization() * 100));
                return bestNode.id;
            }

            // Try preemption: evict lower priority allocations
            for (Node node : nodes) {
                ResourceRequest victim = findPreemptionVictim(node, request);
                if (victim != null) {
                    node.deallocate(victim);
                    node.allocate(request);
                    allocated++;
                    log.add(String.format("  PREEMPT %s evicted by %s on %s",
                            victim.id, request.id, node.id));
                    pendingQueue.offer(victim); // Re-queue victim
                    return node.id;
                }
            }

            rejected++;
            log.add(String.format("  REJECT %s (no capacity, priority=%d)", request.id, request.priority));
            return null;
        }

        private ResourceRequest findPreemptionVictim(Node node, ResourceRequest request) {
            for (ResourceRequest alloc : node.allocations) {
                if (alloc.priority > request.priority) { // lower priority = preemptable
                    if (node.canFit(request) ||
                        (node.totalCpu - node.usedCpu + alloc.cpuNeeded >= request.cpuNeeded &&
                         node.totalMemory - node.usedMemory + alloc.memoryNeeded >= request.memoryNeeded)) {
                        return alloc;
                    }
                }
            }
            return null;
        }

        void printClusterState() {
            System.out.println("\nCluster state:");
            for (Node n : nodes) {
                System.out.printf("  %s: cpu=%d/%d mem=%d/%d util=%.0f%% allocs=%d%n",
                        n.id, n.usedCpu, n.totalCpu, n.usedMemory, n.totalMemory,
                        n.utilization() * 100, n.allocations.size());
            }
            System.out.printf("  Total: %d allocated, %d rejected%n", allocated, rejected);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Capacity-Aware Resource Allocator ===\n");

        ResourceAllocator allocator = new ResourceAllocator();
        allocator.addNode(new Node("node-1", 8, 16));
        allocator.addNode(new Node("node-2", 8, 16));
        allocator.addNode(new Node("node-3", 4, 8));

        ResourceRequest[] requests = {
            new ResourceRequest("web-server", 2, 2, 4),
            new ResourceRequest("database", 1, 4, 8),
            new ResourceRequest("cache", 2, 2, 4),
            new ResourceRequest("worker-1", 3, 2, 2),
            new ResourceRequest("worker-2", 3, 2, 2),
            new ResourceRequest("ml-training", 1, 6, 12), // High priority, needs preemption
            new ResourceRequest("batch-job", 4, 4, 8),
        };

        for (ResourceRequest req : requests) {
            allocator.allocate(req);
        }

        allocator.log.forEach(System.out::println);
        allocator.printClusterState();
    }
}
