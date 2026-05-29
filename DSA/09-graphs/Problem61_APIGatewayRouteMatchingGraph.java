import java.util.*;

/**
 * Problem 61: API Gateway Route Matching Graph
 * 
 * Production Relevance:
 * - API gateways (Kong, NGINX, AWS API Gateway) match incoming paths to backend handlers
 * - Route tree with wildcards, path params, priority-based conflict resolution
 * - Must be O(path_segments) not O(num_routes) for high-throughput gateways
 * - Used in reverse proxies, service meshes, serverless function routing
 * 
 * Architect Considerations:
 * - Trie/radix tree structure for efficient prefix matching
 * - Priority: exact > param > wildcard
 * - Middleware chaining at each route node
 */
public class Problem61_APIGatewayRouteMatchingGraph {

    enum NodeType { EXACT, PARAM, WILDCARD }

    static class RouteNode {
        String segment;
        NodeType type;
        String paramName;
        Map<String, RouteNode> exactChildren = new HashMap<>();
        RouteNode paramChild;
        RouteNode wildcardChild;
        String handler;
        List<String> middlewares = new ArrayList<>();

        RouteNode(String segment, NodeType type) {
            this.segment = segment; this.type = type;
            if (type == NodeType.PARAM) this.paramName = segment.substring(1); // strip ':'
        }
    }

    static class MatchResult {
        String handler;
        Map<String, String> params;
        List<String> middlewares;

        MatchResult(String handler, Map<String, String> params, List<String> middlewares) {
            this.handler = handler; this.params = params; this.middlewares = middlewares;
        }

        @Override
        public String toString() {
            return String.format("handler=%s, params=%s, middlewares=%s", handler, params, middlewares);
        }
    }

    static class RouteTree {
        RouteNode root = new RouteNode("", NodeType.EXACT);

        void addRoute(String method, String path, String handler, String... middlewares) {
            String key = method + ":" + path;
            String[] segments = path.split("/");
            RouteNode current = root;

            for (int i = 1; i < segments.length; i++) {
                String seg = segments[i];
                if (seg.startsWith(":")) {
                    if (current.paramChild == null) current.paramChild = new RouteNode(seg, NodeType.PARAM);
                    current = current.paramChild;
                } else if (seg.equals("*")) {
                    if (current.wildcardChild == null) current.wildcardChild = new RouteNode(seg, NodeType.WILDCARD);
                    current = current.wildcardChild;
                    break; // wildcard catches rest
                } else {
                    current.exactChildren.computeIfAbsent(seg, s -> new RouteNode(s, NodeType.EXACT));
                    current = current.exactChildren.get(seg);
                }
            }
            current.handler = handler;
            current.middlewares = Arrays.asList(middlewares);
        }

        MatchResult match(String method, String path) {
            String[] segments = path.split("/");
            Map<String, String> params = new LinkedHashMap<>();
            List<String> middlewares = new ArrayList<>();
            RouteNode result = matchRecursive(root, segments, 1, params, middlewares);
            if (result != null && result.handler != null) {
                middlewares.addAll(result.middlewares);
                return new MatchResult(result.handler, params, middlewares);
            }
            return null;
        }

        private RouteNode matchRecursive(RouteNode node, String[] segments, int idx,
                                          Map<String, String> params, List<String> middlewares) {
            if (idx >= segments.length) return node;
            String seg = segments[idx];

            // Priority: exact > param > wildcard
            if (node.exactChildren.containsKey(seg)) {
                RouteNode result = matchRecursive(node.exactChildren.get(seg), segments, idx + 1, params, middlewares);
                if (result != null && result.handler != null) return result;
            }
            if (node.paramChild != null) {
                params.put(node.paramChild.paramName, seg);
                RouteNode result = matchRecursive(node.paramChild, segments, idx + 1, params, middlewares);
                if (result != null && result.handler != null) return result;
                params.remove(node.paramChild.paramName);
            }
            if (node.wildcardChild != null) {
                String rest = String.join("/", Arrays.copyOfRange(segments, idx, segments.length));
                params.put("*", rest);
                return node.wildcardChild;
            }
            return null;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== API Gateway Route Matching Graph ===\n");

        RouteTree router = new RouteTree();
        router.addRoute("GET", "/api/users", "listUsers", "auth", "rateLimit");
        router.addRoute("GET", "/api/users/:id", "getUser", "auth");
        router.addRoute("GET", "/api/users/:id/orders", "getUserOrders", "auth");
        router.addRoute("POST", "/api/users", "createUser", "auth", "validate");
        router.addRoute("GET", "/api/health", "healthCheck");
        router.addRoute("GET", "/static/*", "serveStatic", "cache");

        String[][] tests = {
            {"GET", "/api/users"},
            {"GET", "/api/users/123"},
            {"GET", "/api/users/456/orders"},
            {"GET", "/api/health"},
            {"GET", "/static/css/main.css"},
            {"GET", "/api/unknown"},
        };

        for (String[] test : tests) {
            MatchResult result = router.match(test[0], test[1]);
            System.out.printf("%-5s %-30s -> %s%n", test[0], test[1],
                    result != null ? result : "404 NOT FOUND");
        }
    }
}
