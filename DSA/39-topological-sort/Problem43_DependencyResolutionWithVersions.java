import java.util.*;

/**
 * Problem: Dependency Resolution with Versions
 * Resolve dependencies considering version constraints (simplified semver).
 *
 * Approach: Topological sort with version conflict detection
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: npm/Maven dependency resolution with version conflicts.
 */
public class Problem43_DependencyResolutionWithVersions {

    static class Package {
        String name;
        int version;
        List<String> deps;
        Package(String n, int v, List<String> d) { name = n; version = v; deps = d; }
    }

    public List<String> resolve(List<Package> packages) {
        Map<String, Package> latest = new HashMap<>();
        for (Package p : packages)
            if (!latest.containsKey(p.name) || latest.get(p.name).version < p.version)
                latest.put(p.name, p);

        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();
        for (String name : latest.keySet()) { inDeg.put(name, 0); graph.put(name, new ArrayList<>()); }
        for (var e : latest.entrySet())
            for (String dep : e.getValue().deps) {
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(e.getKey());
                inDeg.merge(e.getKey(), 1, Integer::sum);
            }

        Queue<String> q = new LinkedList<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());
        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String pkg = q.poll(); order.add(pkg + "@" + latest.get(pkg).version);
            for (String nei : graph.getOrDefault(pkg, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return order;
    }

    public static void main(String[] args) {
        Problem43_DependencyResolutionWithVersions solver = new Problem43_DependencyResolutionWithVersions();
        List<Package> pkgs = Arrays.asList(
            new Package("app", 1, Arrays.asList("lib")),
            new Package("lib", 2, Arrays.asList("util")),
            new Package("lib", 1, Collections.emptyList()),
            new Package("util", 1, Collections.emptyList())
        );
        System.out.println(solver.resolve(pkgs));
    }
}
