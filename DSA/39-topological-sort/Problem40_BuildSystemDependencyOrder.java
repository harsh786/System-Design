import java.util.*;

/**
 * Problem: Build System Dependency Order
 * Resolve build targets considering transitive dependencies.
 *
 * Approach: DFS topological sort collecting all transitive deps
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Make/Bazel build target resolution.
 */
public class Problem40_BuildSystemDependencyOrder {

    public List<String> buildOrder(String target, Map<String, List<String>> deps) {
        Set<String> visited = new LinkedHashSet<>();
        dfs(target, deps, visited, new HashSet<>());
        return new ArrayList<>(visited);
    }

    private void dfs(String node, Map<String, List<String>> deps, Set<String> visited, Set<String> path) {
        if (visited.contains(node)) return;
        if (path.contains(node)) throw new RuntimeException("Cycle detected: " + node);
        path.add(node);
        for (String dep : deps.getOrDefault(node, Collections.emptyList()))
            dfs(dep, deps, visited, path);
        path.remove(node);
        visited.add(node);
    }

    public static void main(String[] args) {
        Problem40_BuildSystemDependencyOrder solver = new Problem40_BuildSystemDependencyOrder();
        Map<String, List<String>> deps = new HashMap<>();
        deps.put("app", Arrays.asList("lib", "utils"));
        deps.put("lib", Arrays.asList("utils"));
        deps.put("utils", Collections.emptyList());
        System.out.println(solver.buildOrder("app", deps)); // [utils, lib, app]
    }
}
