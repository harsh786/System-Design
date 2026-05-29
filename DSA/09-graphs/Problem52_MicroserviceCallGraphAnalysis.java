import java.util.*;

/**
 * Problem 52: Microservice Call Graph Analysis
 * 
 * Production Relevance:
 * - Service mesh observability: find critical paths, bottlenecks, single points of failure
 * - Detect cascading failure paths, compute blast radius of service outages
 * - Used in distributed tracing (Jaeger, Zipkin), service dependency mapping
 * - Enables chaos engineering targeting: which service failure has highest impact?
 * 
 * Architect Considerations:
 * - Dynamic graph: edges added/removed as services deploy
 * - Weighted edges (latency, error rate, throughput)
 * - Critical path = longest path in DAG (determines end-to-end latency)
 */
public class Problem52_MicroserviceCallGraphAnalysis {

    static class ServiceEdge {
        String target;
        double avgLatencyMs;
        double errorRate;
        int callsPerSecond;

        ServiceEdge(String target, double latency, double errorRate, int qps) {
            this.target = target; this.avgLatencyMs = latency;
            this.errorRate = errorRate; this.callsPerSecond = qps;
        }
    }

    static class CallGraph {
        Map<String, List<ServiceEdge>> adjacency = new HashMap<>();
        Set<String> services = new HashSet<>();

        void addEdge(String from, String to, double latency, double errorRate, int qps) {
            services.add(from);
            services.add(to);
            adjacency.computeIfAbsent(from, k -> new ArrayList<>())
                    .add(new ServiceEdge(to, latency, errorRate, qps));
        }

        // Find critical path (longest latency path from entry point)
        Map.Entry<List<String>, Double> criticalPath(String source) {
            Map<String, Double> maxDist = new HashMap<>();
            Map<String, String> prev = new HashMap<>();
            // Topological sort + longest path
            List<String> topoOrder = topologicalSort();
            for (String s : services) maxDist.put(s, Double.NEGATIVE_INFINITY);
            maxDist.put(source, 0.0);

            for (String u : topoOrder) {
                if (maxDist.get(u) == Double.NEGATIVE_INFINITY) continue;
                for (ServiceEdge edge : adjacency.getOrDefault(u, List.of())) {
                    double newDist = maxDist.get(u) + edge.avgLatencyMs;
                    if (newDist > maxDist.getOrDefault(edge.target, Double.NEGATIVE_INFINITY)) {
                        maxDist.put(edge.target, newDist);
                        prev.put(edge.target, u);
                    }
                }
            }

            // Find longest endpoint
            String end = source;
            for (Map.Entry<String, Double> e : maxDist.entrySet()) {
                if (e.getValue() > maxDist.get(end)) end = e.getKey();
            }

            // Reconstruct path
            List<String> path = new ArrayList<>();
            for (String at = end; at != null; at = prev.get(at)) path.add(at);
            Collections.reverse(path);
            return Map.entry(path, maxDist.get(end));
        }

        // Blast radius: how many services are affected if 'service' goes down
        Set<String> blastRadius(String service) {
            Set<String> affected = new HashSet<>();
            Queue<String> queue = new LinkedList<>();
            queue.offer(service);
            while (!queue.isEmpty()) {
                String curr = queue.poll();
                for (ServiceEdge edge : adjacency.getOrDefault(curr, List.of())) {
                    if (affected.add(edge.target)) queue.offer(edge.target);
                }
            }
            return affected;
        }

        // Single points of failure (articulation points)
        Set<String> findSPOF() {
            Set<String> spof = new HashSet<>();
            Map<String, Integer> disc = new HashMap<>(), low = new HashMap<>();
            Map<String, String> parent = new HashMap<>();
            int[] time = {0};

            for (String s : services) {
                if (!disc.containsKey(s)) dfsArticulation(s, disc, low, parent, spof, time);
            }
            return spof;
        }

        private void dfsArticulation(String u, Map<String, Integer> disc, Map<String, Integer> low,
                                      Map<String, String> parent, Set<String> spof, int[] time) {
            disc.put(u, time[0]);
            low.put(u, time[0]);
            time[0]++;
            int children = 0;

            for (ServiceEdge edge : adjacency.getOrDefault(u, List.of())) {
                String v = edge.target;
                if (!disc.containsKey(v)) {
                    children++;
                    parent.put(v, u);
                    dfsArticulation(v, disc, low, parent, spof, time);
                    low.put(u, Math.min(low.get(u), low.get(v)));
                    if (parent.get(u) == null && children > 1) spof.add(u);
                    if (parent.get(u) != null && low.get(v) >= disc.get(u)) spof.add(u);
                } else if (!v.equals(parent.get(u))) {
                    low.put(u, Math.min(low.get(u), disc.get(v)));
                }
            }
        }

        private List<String> topologicalSort() {
            Map<String, Integer> inDeg = new HashMap<>();
            services.forEach(s -> inDeg.put(s, 0));
            adjacency.forEach((u, edges) -> edges.forEach(e -> inDeg.merge(e.target, 1, Integer::sum)));
            Queue<String> q = new LinkedList<>();
            inDeg.forEach((s, d) -> { if (d == 0) q.offer(s); });
            List<String> order = new ArrayList<>();
            while (!q.isEmpty()) {
                String u = q.poll();
                order.add(u);
                for (ServiceEdge e : adjacency.getOrDefault(u, List.of())) {
                    if (inDeg.merge(e.target, -1, Integer::sum) == 0) q.offer(e.target);
                }
            }
            return order;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Microservice Call Graph Analysis ===\n");

        CallGraph graph = new CallGraph();
        graph.addEdge("api-gateway", "auth-service", 5, 0.001, 1000);
        graph.addEdge("api-gateway", "order-service", 10, 0.005, 500);
        graph.addEdge("order-service", "inventory-service", 15, 0.01, 500);
        graph.addEdge("order-service", "payment-service", 50, 0.02, 500);
        graph.addEdge("payment-service", "fraud-detection", 30, 0.005, 500);
        graph.addEdge("inventory-service", "warehouse-service", 20, 0.001, 200);

        // Critical path
        var cp = graph.criticalPath("api-gateway");
        System.out.println("Critical path: " + cp.getKey() + " (total latency: " + cp.getValue() + "ms)");

        // Blast radius
        System.out.println("\nBlast radius of order-service failure: " + graph.blastRadius("order-service"));
        System.out.println("Blast radius of payment-service failure: " + graph.blastRadius("payment-service"));

        // SPOFs
        System.out.println("\nSingle points of failure: " + graph.findSPOF());
    }
}
