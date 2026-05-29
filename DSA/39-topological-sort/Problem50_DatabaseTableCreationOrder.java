import java.util.*;

/**
 * Problem: Database Table Creation Order
 * Order CREATE TABLE statements respecting foreign key dependencies.
 *
 * Approach: Topological sort where FK references create edges
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: ORM migration generation for relational databases.
 */
public class Problem50_DatabaseTableCreationOrder {

    public List<String> creationOrder(Map<String, List<String>> foreignKeys) {
        Map<String, Integer> inDeg = new HashMap<>();
        Map<String, List<String>> graph = new HashMap<>();

        for (String table : foreignKeys.keySet()) {
            inDeg.putIfAbsent(table, 0);
            graph.putIfAbsent(table, new ArrayList<>());
            for (String ref : foreignKeys.get(table)) {
                graph.computeIfAbsent(ref, k -> new ArrayList<>()).add(table);
                inDeg.merge(table, 1, Integer::sum);
                inDeg.putIfAbsent(ref, 0);
            }
        }

        Queue<String> q = new PriorityQueue<>();
        for (var e : inDeg.entrySet()) if (e.getValue() == 0) q.offer(e.getKey());

        List<String> order = new ArrayList<>();
        while (!q.isEmpty()) {
            String t = q.poll(); order.add(t);
            for (String nei : graph.getOrDefault(t, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return order.size() == inDeg.size() ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem50_DatabaseTableCreationOrder solver = new Problem50_DatabaseTableCreationOrder();
        Map<String, List<String>> fks = new HashMap<>();
        fks.put("orders", Arrays.asList("users", "products"));
        fks.put("users", Collections.emptyList());
        fks.put("products", Arrays.asList("categories"));
        fks.put("categories", Collections.emptyList());
        System.out.println(solver.creationOrder(fks));
    }
}
