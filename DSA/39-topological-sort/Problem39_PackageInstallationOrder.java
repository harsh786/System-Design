import java.util.*;

/**
 * Problem: Package Installation Order
 * Determine package install order respecting dependencies (like apt/npm).
 *
 * Approach: Topological sort on package dependency graph
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Package manager dependency resolution (npm, pip, apt).
 */
public class Problem39_PackageInstallationOrder {

    public List<String> installOrder(Map<String, List<String>> packages) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String pkg : packages.keySet()) {
            inDeg.putIfAbsent(pkg, 0);
            graph.putIfAbsent(pkg, new ArrayList<>());
            for (String dep : packages.get(pkg)) {
                inDeg.putIfAbsent(dep, 0);
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(pkg);
                inDeg.merge(pkg, 1, Integer::sum);
            }
        }

        Queue<String> q = new PriorityQueue<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String pkg = q.poll(); order.add(pkg);
            for (String dep : graph.getOrDefault(pkg, Collections.emptyList()))
                if (inDeg.merge(dep, -1, Integer::sum) == 0) q.offer(dep);
        }
        return order.size() == inDeg.size() ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem39_PackageInstallationOrder solver = new Problem39_PackageInstallationOrder();
        Map<String, List<String>> pkgs = new HashMap<>();
        pkgs.put("express", Arrays.asList("body-parser", "cookie"));
        pkgs.put("body-parser", Collections.emptyList());
        pkgs.put("cookie", Collections.emptyList());
        System.out.println(solver.installOrder(pkgs));
    }
}
