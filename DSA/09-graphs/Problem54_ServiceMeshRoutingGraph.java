import java.util.*;

/**
 * Problem 54: Service Mesh Routing Graph
 * 
 * Production Relevance:
 * - Istio/Envoy service mesh routes traffic based on rules: canary, A/B, weighted routing
 * - Virtual services + destination rules form a graph of routing decisions
 * - Must compute effective route for a request through proxy chain
 * - Used for traffic splitting, fault injection, circuit breaking decisions
 * 
 * Architect Considerations:
 * - Route precedence: most specific match wins (path > header > default)
 * - Weighted routing for canary deployments (e.g., 5% to v2)
 * - Retry and timeout policies per route segment
 * - mTLS enforcement graph: which paths require mutual TLS
 */
public class Problem54_ServiceMeshRoutingGraph {

    static class RouteRule {
        String matchPath;
        Map<String, String> matchHeaders;
        List<WeightedDestination> destinations;
        int retries;
        long timeoutMs;

        RouteRule(String path, Map<String, String> headers, List<WeightedDestination> dests, int retries, long timeout) {
            this.matchPath = path; this.matchHeaders = headers;
            this.destinations = dests; this.retries = retries; this.timeoutMs = timeout;
        }

        int specificity() {
            int s = 0;
            if (matchPath != null && !matchPath.equals("*")) s += 10;
            s += matchHeaders.size() * 5;
            return s;
        }
    }

    static class WeightedDestination {
        String service;
        String version;
        int weight; // percentage

        WeightedDestination(String service, String version, int weight) {
            this.service = service; this.version = version; this.weight = weight;
        }

        @Override
        public String toString() { return service + ":" + version + "(" + weight + "%)"; }
    }

    static class ServiceMeshRouter {
        // service -> list of route rules (ordered by priority)
        Map<String, List<RouteRule>> virtualServices = new LinkedHashMap<>();

        void addVirtualService(String service, RouteRule... rules) {
            List<RouteRule> ruleList = Arrays.asList(rules);
            ruleList.sort((a, b) -> Integer.compare(b.specificity(), a.specificity()));
            virtualServices.put(service, ruleList);
        }

        // Resolve route for a request
        WeightedDestination route(String service, String path, Map<String, String> headers) {
            List<RouteRule> rules = virtualServices.get(service);
            if (rules == null) return new WeightedDestination(service, "v1", 100);

            for (RouteRule rule : rules) {
                if (matches(rule, path, headers)) {
                    return selectByWeight(rule.destinations);
                }
            }
            return new WeightedDestination(service, "v1", 100); // default
        }

        private boolean matches(RouteRule rule, String path, Map<String, String> headers) {
            if (rule.matchPath != null && !rule.matchPath.equals("*")) {
                if (!path.startsWith(rule.matchPath)) return false;
            }
            for (Map.Entry<String, String> h : rule.matchHeaders.entrySet()) {
                if (!h.getValue().equals(headers.get(h.getKey()))) return false;
            }
            return true;
        }

        private WeightedDestination selectByWeight(List<WeightedDestination> dests) {
            int roll = new Random().nextInt(100);
            int cumulative = 0;
            for (WeightedDestination d : dests) {
                cumulative += d.weight;
                if (roll < cumulative) return d;
            }
            return dests.get(dests.size() - 1);
        }

        // Compute full request path through mesh
        List<String> traceRoute(String entryService, String path, Map<String, String> headers,
                                Map<String, List<String>> callGraph) {
            List<String> trace = new ArrayList<>();
            Queue<String> queue = new LinkedList<>();
            queue.offer(entryService);
            Set<String> visited = new HashSet<>();

            while (!queue.isEmpty()) {
                String svc = queue.poll();
                if (!visited.add(svc)) continue;
                WeightedDestination dest = route(svc, path, headers);
                trace.add(svc + " -> " + dest);
                for (String downstream : callGraph.getOrDefault(svc, List.of())) {
                    queue.offer(downstream);
                }
            }
            return trace;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Service Mesh Routing Graph ===\n");

        ServiceMeshRouter router = new ServiceMeshRouter();

        // Canary deployment: 90% v1, 10% v2
        router.addVirtualService("product-service",
            new RouteRule("/api/products", Map.of("x-canary", "true"),
                List.of(new WeightedDestination("product-service", "v2", 100)), 3, 5000),
            new RouteRule("*", Map.of(),
                List.of(new WeightedDestination("product-service", "v1", 90),
                        new WeightedDestination("product-service", "v2", 10)), 2, 3000)
        );

        // Route requests
        System.out.println("Normal request:");
        for (int i = 0; i < 5; i++) {
            WeightedDestination d = router.route("product-service", "/api/products", Map.of());
            System.out.println("  -> " + d);
        }

        System.out.println("\nCanary header request:");
        WeightedDestination d = router.route("product-service", "/api/products", Map.of("x-canary", "true"));
        System.out.println("  -> " + d + " (always v2 with canary header)");

        // Trace full route
        Map<String, List<String>> callGraph = Map.of(
            "api-gateway", List.of("product-service", "user-service"),
            "product-service", List.of("inventory-service")
        );
        System.out.println("\nFull route trace:");
        router.traceRoute("api-gateway", "/api/products", Map.of(), callGraph)
              .forEach(t -> System.out.println("  " + t));
    }
}
