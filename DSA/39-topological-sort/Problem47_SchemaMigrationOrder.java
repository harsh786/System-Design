import java.util.*;

/**
 * Problem: Schema Migration Order
 * Order database migrations respecting dependencies between them.
 *
 * Approach: Topological sort on migration dependency graph
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Flyway/Liquibase migration ordering with cross-references.
 */
public class Problem47_SchemaMigrationOrder {

    public List<String> migrationOrder(Map<String, List<String>> migrations) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String m : migrations.keySet()) {
            inDeg.putIfAbsent(m, 0);
            graph.putIfAbsent(m, new ArrayList<>());
            for (String dep : migrations.get(m)) {
                graph.computeIfAbsent(dep, k -> new ArrayList<>()).add(m);
                inDeg.merge(m, 1, Integer::sum);
                inDeg.putIfAbsent(dep, 0);
            }
        }

        Queue<String> q = new PriorityQueue<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String m = q.poll(); order.add(m);
            for (String nei : graph.getOrDefault(m, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return order.size() == inDeg.size() ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem47_SchemaMigrationOrder solver = new Problem47_SchemaMigrationOrder();
        Map<String, List<String>> migs = new HashMap<>();
        migs.put("003_add_index", Arrays.asList("001_create_table"));
        migs.put("002_add_column", Arrays.asList("001_create_table"));
        migs.put("001_create_table", Collections.emptyList());
        System.out.println(solver.migrationOrder(migs));
    }
}
