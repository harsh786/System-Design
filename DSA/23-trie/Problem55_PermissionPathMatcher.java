import java.util.*;

/**
 * Problem 55: Permission Path Matcher
 * 
 * Production Relevance:
 * - RBAC/ABAC systems: check if user has permission for resource path
 * - AWS IAM policies use path matching: "arn:aws:s3:::bucket/prefix/*"
 * - File system ACLs: /home/user/** grants access to all sub-paths
 * - Used in API authorization, file permissions, Kubernetes RBAC
 * 
 * Architect Considerations:
 * - Wildcards at different levels: single-segment (*) vs recursive (**)
 * - Deny overrides allow (explicit deny wins)
 * - Permission evaluation must be O(path_length) for every request
 * - Caching evaluated permissions with cache invalidation on policy change
 */
public class Problem55_PermissionPathMatcher {

    enum Permission { ALLOW, DENY, UNSET }
    enum Action { READ, WRITE, DELETE, ADMIN }

    static class PolicyNode {
        Map<String, PolicyNode> children = new HashMap<>();
        PolicyNode singleWildcard; // matches one segment (*)
        PolicyNode recursiveWildcard; // matches all remaining (**)
        Map<Action, Permission> permissions = new EnumMap<>(Action.class);
    }

    static class PermissionSystem {
        PolicyNode root = new PolicyNode();

        // Add policy: e.g., path="/api/users/**", action=READ, perm=ALLOW
        void addPolicy(String path, Action action, Permission permission) {
            String[] segments = path.split("/");
            PolicyNode node = root;

            for (int i = 1; i < segments.length; i++) {
                String seg = segments[i];
                if (seg.equals("**")) {
                    if (node.recursiveWildcard == null) node.recursiveWildcard = new PolicyNode();
                    node = node.recursiveWildcard;
                    break;
                } else if (seg.equals("*")) {
                    if (node.singleWildcard == null) node.singleWildcard = new PolicyNode();
                    node = node.singleWildcard;
                } else {
                    node.children.computeIfAbsent(seg, k -> new PolicyNode());
                    node = node.children.get(seg);
                }
            }
            node.permissions.put(action, permission);
        }

        // Check permission: DENY > ALLOW > UNSET (most specific + deny wins)
        Permission check(String path, Action action) {
            String[] segments = path.split("/");
            List<Permission> collected = new ArrayList<>();
            collectPermissions(root, segments, 1, action, collected);

            // Deny wins
            if (collected.contains(Permission.DENY)) return Permission.DENY;
            if (collected.contains(Permission.ALLOW)) return Permission.ALLOW;
            return Permission.UNSET;
        }

        private void collectPermissions(PolicyNode node, String[] segments, int idx,
                                         Action action, List<Permission> result) {
            // Collect permission at current node
            Permission p = node.permissions.get(action);
            if (p != null) result.add(p);

            // Recursive wildcard matches everything below
            if (node.recursiveWildcard != null) {
                Permission rwp = node.recursiveWildcard.permissions.get(action);
                if (rwp != null) result.add(rwp);
            }

            if (idx >= segments.length) return;
            String seg = segments[idx];

            // Exact match
            if (node.children.containsKey(seg)) {
                collectPermissions(node.children.get(seg), segments, idx + 1, action, result);
            }
            // Single wildcard match
            if (node.singleWildcard != null) {
                collectPermissions(node.singleWildcard, segments, idx + 1, action, result);
            }
            // Recursive wildcard
            if (node.recursiveWildcard != null) {
                collectPermissions(node.recursiveWildcard, segments, idx + 1, action, result);
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Permission Path Matcher ===\n");

        PermissionSystem perms = new PermissionSystem();

        // Policies
        perms.addPolicy("/api/**", Action.READ, Permission.ALLOW);          // Allow read on all API
        perms.addPolicy("/api/admin/**", Action.READ, Permission.DENY);     // But deny admin API
        perms.addPolicy("/api/admin/health", Action.READ, Permission.ALLOW);// Except health check
        perms.addPolicy("/api/users/*", Action.WRITE, Permission.ALLOW);    // Write to specific user
        perms.addPolicy("/api/users/*/secrets", Action.READ, Permission.DENY); // Deny secrets

        String[][] tests = {
            {"/api/products", "READ"},
            {"/api/admin/settings", "READ"},
            {"/api/admin/health", "READ"},
            {"/api/users/123", "WRITE"},
            {"/api/users/123/secrets", "READ"},
            {"/api/users/123", "DELETE"},
        };

        for (String[] test : tests) {
            Permission result = perms.check(test[0], Action.valueOf(test[1]));
            System.out.printf("  %-30s %-6s -> %s%n", test[0], test[1], result);
        }
    }
}
