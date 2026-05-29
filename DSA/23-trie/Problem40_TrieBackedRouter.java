import java.util.*;

/**
 * Problem 40: Trie-backed Router Matching
 * 
 * HTTP router supporting static paths, parameterized segments (:id), and wildcards (*).
 * 
 * Time Complexity: O(segments) per route match
 * Space Complexity: O(total routes * avg segments)
 * 
 * Production Analogy: Express.js/Spring Boot route matching, API gateway routing,
 * nginx location blocks, AWS API Gateway resource paths.
 */
public class Problem40_TrieBackedRouter {

    static class TrieNode {
        Map<String, TrieNode> children = new HashMap<>();
        TrieNode paramChild = null;  // :param
        TrieNode wildcardChild = null; // *
        String paramName = null;
        String handler = null;
    }

    static class Router {
        TrieNode root = new TrieNode();

        void addRoute(String method, String path, String handler) {
            TrieNode node = root;
            String key = method + ":";
            if (!node.children.containsKey(key)) node.children.put(key, new TrieNode());
            node = node.children.get(key);

            String[] segments = path.split("/");
            for (int i = 1; i < segments.length; i++) {
                String seg = segments[i];
                if (seg.startsWith(":")) {
                    if (node.paramChild == null) node.paramChild = new TrieNode();
                    node.paramChild.paramName = seg.substring(1);
                    node = node.paramChild;
                } else if (seg.equals("*")) {
                    if (node.wildcardChild == null) node.wildcardChild = new TrieNode();
                    node = node.wildcardChild;
                    break;
                } else {
                    node.children.putIfAbsent(seg, new TrieNode());
                    node = node.children.get(seg);
                }
            }
            node.handler = handler;
        }

        String match(String method, String path) {
            TrieNode node = root;
            String key = method + ":";
            if (!node.children.containsKey(key)) return null;
            node = node.children.get(key);

            String[] segments = path.split("/");
            Map<String, String> params = new HashMap<>();
            String result = matchHelper(node, segments, 1, params);
            if (result != null) System.out.println("  Params: " + params);
            return result;
        }

        String matchHelper(TrieNode node, String[] segments, int i, Map<String, String> params) {
            if (i == segments.length) return node.handler;
            // Try exact match
            if (node.children.containsKey(segments[i])) {
                String r = matchHelper(node.children.get(segments[i]), segments, i + 1, params);
                if (r != null) return r;
            }
            // Try param match
            if (node.paramChild != null) {
                params.put(node.paramChild.paramName, segments[i]);
                String r = matchHelper(node.paramChild, segments, i + 1, params);
                if (r != null) return r;
                params.remove(node.paramChild.paramName);
            }
            // Try wildcard
            if (node.wildcardChild != null && node.wildcardChild.handler != null) {
                return node.wildcardChild.handler;
            }
            return null;
        }
    }

    public static void main(String[] args) {
        Router router = new Router();
        router.addRoute("GET", "/users", "listUsers");
        router.addRoute("GET", "/users/:id", "getUser");
        router.addRoute("POST", "/users/:id/posts", "createPost");
        router.addRoute("GET", "/static/*", "serveStatic");

        System.out.println(router.match("GET", "/users"));          // listUsers
        System.out.println(router.match("GET", "/users/123"));      // getUser
        System.out.println(router.match("POST", "/users/42/posts"));// createPost
        System.out.println(router.match("GET", "/static/js/app.js"));// serveStatic
        System.out.println(router.match("GET", "/unknown"));        // null
    }
}
