import java.util.*;

/**
 * Problem: Module Compilation Order
 * Determine compilation order for modules with import dependencies.
 *
 * Approach: Topological sort on module dependency graph
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Build system determining compilation order for source modules.
 */
public class Problem26_ModuleCompilationOrder {

    public List<String> compilationOrder(Map<String, List<String>> dependencies) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String mod : dependencies.keySet()) {
            graph.putIfAbsent(mod, new ArrayList<>());
            inDeg.putIfAbsent(mod, 0);
            for (String dep : dependencies.get(mod)) {
                graph.putIfAbsent(dep, new ArrayList<>());
                inDeg.putIfAbsent(dep, 0);
                graph.get(dep).add(mod);
                inDeg.merge(mod, 1, Integer::sum);
            }
        }

        Queue<String> q = new LinkedList<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String mod = q.poll(); order.add(mod);
            for (String nei : graph.get(mod))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return order.size() == inDeg.size() ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem26_ModuleCompilationOrder solver = new Problem26_ModuleCompilationOrder();
        Map<String, List<String>> deps = new HashMap<>();
        deps.put("app", Arrays.asList("utils", "core"));
        deps.put("core", Arrays.asList("utils"));
        deps.put("utils", Collections.emptyList());
        System.out.println(solver.compilationOrder(deps));
    }
}
