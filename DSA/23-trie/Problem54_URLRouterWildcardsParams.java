import java.util.*;

/**
 * Problem 54: URL Router with Wildcards and Params
 * 
 * Production Relevance:
 * - Express.js, Spring MVC, Gin (Go) all use trie-based routers
 * - Must match: exact paths, path params (:id), wildcards (*), regex constraints
 * - O(path_length) lookup regardless of number of registered routes
 * - Used in every web framework, API gateway, reverse proxy
 * 
 * Architect Considerations:
 * - Priority: static > param > wildcard (same as Problem61 but trie-focused)
 * - Path normalization: trailing slashes, double slashes
 * - Method-based routing (GET /users vs POST /users) at same path node
 */
public class Problem54_URLRouterWildcardsParams {

    static class RouteNode {
        Map<String, RouteNode> staticChildren = new HashMap<>();
        RouteNode paramChild;
        String paramName;
        RouteNode wildcardChild;
        Map<String, String> handlers = new HashMap<>(); // method -> handler
    }

    static class Router {
        RouteNode root = new RouteNode();

        void addRoute(String method, String pattern, String handler) {
            String[] parts = pattern.split("/");
            RouteNode node = root;

            for (int i = 1; i < parts.length; i++) {
                String part = parts[i];
                if (part.startsWith(":")) {
                    if (node.paramChild == null) {
                        node.paramChild = new RouteNode();
                        node.paramChild.paramName = part.substring(1);
                    }
                    node = node.paramChild;
                } else if (part.equals("*") || part.startsWith("*")) {
                    if (node.wildcardChild == null) node.wildcardChild = new RouteNode();
                    node = node.wildcardChild;
                    break;
                } else {
                    node.staticChildren.computeIfAbsent(part, k -> new RouteNode());
                    node = node.staticChildren.get(part);
                }
            }
            node.handlers.put(method, handler);
        }

        MatchResult match(String method, String path) {
            String[] parts = path.split("/");
            Map<String, String> params = new LinkedHashMap<>();
            RouteNode node = matchNode(root, parts, 1, params);

            if (node != null && node.handlers.containsKey(method)) {
                return new MatchResult(node.handlers.get(method), params);
            }
            // Check if path exists but method not allowed
            if (node != null && !node.handlers.isEmpty()) {
                return new MatchResult("405 Method Not Allowed", params);
            }
            return null;
        }

        private RouteNode matchNode(RouteNode node, String[] parts, int idx, Map<String, String> params) {
            if (idx >= parts.length) return node;
            String part = parts[idx];

            // Static match (highest priority)
            if (node.staticChildren.containsKey(part)) {
                RouteNode result = matchNode(node.staticChildren.get(part), parts, idx + 1, params);
                if (result != null && !result.handlers.isEmpty()) return result;
            }
            // Param match
            if (node.paramChild != null) {
                params.put(node.paramChild.paramName, part);
                RouteNode result = matchNode(node.paramChild, parts, idx + 1, params);
                if (result != null && !result.handlers.isEmpty()) return result;
                params.remove(node.paramChild.paramName);
            }
            // Wildcard match (catches all remaining)
            if (node.wildcardChild != null) {
                String remaining = String.join("/", Arrays.copyOfRange(parts, idx, parts.length));
                params.put("*", remaining);
                return node.wildcardChild;
            }
            return node.handlers.isEmpty() ? null : node;
        }
    }

    static class MatchResult {
        String handler;
        Map<String, String> params;

        MatchResult(String handler, Map<String, String> params) {
            this.handler = handler; this.params = params;
        }

        @Override
        public String toString() { return handler + " params=" + params; }
    }

    public static void main(String[] args) {
        System.out.println("=== URL Router with Wildcards and Params ===\n");

        Router router = new Router();
        router.addRoute("GET", "/api/users", "listUsers");
        router.addRoute("POST", "/api/users", "createUser");
        router.addRoute("GET", "/api/users/:userId", "getUser");
        router.addRoute("GET", "/api/users/:userId/posts/:postId", "getUserPost");
        router.addRoute("GET", "/static/*", "serveStatic");
        router.addRoute("GET", "/health", "healthCheck");

        String[][] tests = {
            {"GET", "/api/users"},
            {"POST", "/api/users"},
            {"GET", "/api/users/123"},
            {"GET", "/api/users/456/posts/789"},
            {"GET", "/static/js/app.min.js"},
            {"GET", "/health"},
            {"DELETE", "/api/users"},  // method not allowed
            {"GET", "/not/found"},
        };

        for (String[] test : tests) {
            MatchResult result = router.match(test[0], test[1]);
            System.out.printf("  %-6s %-35s -> %s%n", test[0], test[1],
                    result != null ? result : "404 Not Found");
        }
    }
}
