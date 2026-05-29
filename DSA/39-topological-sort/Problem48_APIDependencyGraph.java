import java.util.*;

/**
 * Problem: API Dependency Graph
 * Determine API initialization order based on cross-API dependencies.
 *
 * Approach: Topological sort with cycle detection for circular API deps
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: API gateway routing setup order based on service dependencies.
 */
public class Problem48_APIDependencyGraph {

    public List<String> initOrder(Map<String, List<String>> apis) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String api : apis.keySet()) {
            inDeg.putIfAbsent(api, 0);
            graph.putIfAbsent(api, new ArrayList<>());
            for (String dep : apis.get(api)) {
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(api);
                inDeg.merge(api, 1, Integer::sum);
                inDeg.putIfAbsent(dep, 0);
            }
        }

        Queue<String> q = new LinkedList<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String api = q.poll(); order.add(api);
            for (String nei : graph.getOrDefault(api, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        if (order.size() != inDeg.size()) throw new RuntimeException("Circular dependency detected!");
        return order;
    }

    public static void main(String[] args) {
        Problem48_APIDependencyGraph solver = new Problem48_APIDependencyGraph();
        Map<String, List<String>> apis = new HashMap<>();
        apis.put("/users", Collections.emptyList());
        apis.put("/orders", Arrays.asList("/users", "/products"));
        apis.put("/products", Collections.emptyList());
        System.out.println(solver.initOrder(apis));
    }
}
